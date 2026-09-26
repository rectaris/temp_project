# Connect the evidence-backed integration review to the exact assembled member result

status: backlog
primary_invariant: A schema-2 member result can be published only when its exact final-base assembly has the latest evidence-backed review accepted through the bound integration session and the same member review budget.
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"record_bounded_review in scripts/plan-execution-state.py rebuilds the Namespace without integration_session_id or integration_session_pid, although spend_group_member_review reads both and post-handoff group review requires them.","kind":"existing_mechanism"}
  - {"evidence":"spend_group_member_review passes the receipt review_target_digest as assembly_record_digest, while parent_direct_review_identity hashes patch bytes and run-parallel-plans.py reviews_of_assembly compares against the assembly record digest.","kind":"existing_mechanism"}
  - {"evidence":"run-parallel-plans.py already verifies submitted handoffs and creates a final-base assembly record; plan-execution-state.py already verifies reviewer receipts, runtime evidence, verdicts and registry admission.","kind":"existing_mechanism"}
  - {"evidence":"Checked plan 384 implements bound reviewer verdict parsing. Existing ParentDirectMemberSessionTests exercise assembly and publication, but direct group review recording is not evidence that the bounded-review command composes with them.","kind":"existing_mechanism"}
completion_conditions:
  - The bound integration session can record a post-handoff review through the real bounded-review command; missing, foreign or stale session identity refuses without granting a review or publication.
  - The review packet, receipt, ledger and publication distinguish the exact assembled patch digest from the assembly-record digest and bind both to the same verified current-base assembly without rebasing or replacing the member ledger.
  - A then B publish from their respective final-base assemblies using evidence-backed reviews; a changed assembly, stale target, missing verdict, latest High or Medium finding, or spent budget refuses.
  - Root and generated commands and instructions expose the same integration review path.
completion_witness_map:
  - {"condition_sha256":"sha256:6972e9fd4639a4b89b4492df652f8d895001d654a19bd3c833fdbd4f37ab594a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:5fb4bfcb4938155a46a2737e6a37c95e83cb3a471dd8ba83529e94602ae830ab","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:ef41416e30c396e44cc8e68afd4535b7b98b3ed38d9d2704264d3c9ac65912be","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0af7a11494f308a17b935a8aa0e638b1e2a32223ac032c6a85fbe15446cf5012","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - tests/test-plan-execution-state.py
  - tests/test-sandboxed-plan-worker.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
preservation_scope:
  - none
context_files:
  - docs/plan/checked/2026/09/16-31/384-derive-review-outcome-from-reviewer-evidence.md
  - docs/plan/checked/2026/09/16-31/373-run-parent-direct-plans-in-member-sessions.md
  - docs/plan/parallel-session-development-20260926.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A post-handoff schema-2 assembly is reviewed through the evidence-backed bounded-review path by its bound integration session and that exact accepted assembly can publish; another session, target, assembly or latest blocking verdict cannot substitute, and member and cumulative review limits are unchanged.
  - Root and generated review commands and guidance remain aligned.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:45fa814209b126a5478338d29c4dc2b336e6b3b939f0039e4a05eb8edf2ef729","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:2e878e71284caa3bcd6fe256c0c8dbd898ab7e776402d0c93ebbb04fa1bf3e80","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Keep plan 379 stopped and shelved. No legacy unforgeability repair or retained candidate is admitted by this plan.
  - Do not announce real-session parallel development as demonstrated from this plan alone; the lifecycle and transcript prerequisites in the operational roadmap must also be completed.
checked_summary_ja: 引き渡し後の統合結果を、証拠付きレビューと結び付けて反映する

## Decisions

- Keep one invariant: publication consumes a valid evidence-backed review of this exact final-base member assembly. Session routing and digest correspondence are parts of that admission, not independent new frameworks.
- Add the bounded integration-assembly input to the existing review path and derive identities from the verified adapter record. Do not equate a patch digest with a record digest or overwrite the source_head of the existing member ledger.
- Authenticate the existing integration session and verify assembly identity before mutable reviewer admission or group-budget effects. Preserve the existing documented recovery rules for later interrupted multi-record effects.
- Keep the original logical member budget, canonical reviewer registry, reserved post-handoff slot and exact-target preflight. The latest review for the exact assembly must clear High and Medium; a count or caller-only group event is not acceptance.
- Reuse checked384 verdict semantics and current receipt validation. Historical records remain readable; an old group review count alone never authorizes a new schema-2 publication.
- Run this plan serially. Do not use the parallel path being changed to implement or accept its own controls.

## Tasks

- [ ] Reproduce the post-handoff bounded-review refusal in an isolated fixture through the actual command, using valid reviewer transcript evidence rather than a mocked forwarding assertion.
- [ ] Propagate the bound integration identity and resolve the verified final-base assembly through packet, preflight, receipt, ledger and group admission without restarting member execution.
- [ ] Bind the assembled patch and assembly record as distinct values; make publication consume the latest accepted review of that verified assembly rather than an arbitrary event or older successful review.
- [ ] Exercise A publication followed by B assembly and review at the new target; preserve the original member ledger source binding and budget.
- [ ] Cover missing/wrong/stale integration identity, replaced assembly, changed target, missing verdict, latest blocking verdict and review exhaustion using consumer-visible refusals.
- [ ] Mirror scripts and instructions, run focused commands, perform an isolated actual CLI review-to-publication smoke, then run the unchanged authoritative suite once on the accepted candidate.

## Validation Notes

- Planning request 2026-09-26: 「並列実装をするためのプランを作成せよ。」 This task authors backlog plans only; implementation and design approval remain separate.
- Planning baseline: c704d857e1e5826dcc96dba6a2fc5513e953aa97. Parent inspected the actual command path after bounded read-only review; no new live-session run or defect regression was executed during authoring.
- Do not reopen the exhausted plan-379 ledgers, apply its unaccepted retained patch, or claim same-user evidence unforgeability. Preserve existing stopped runs and budgets. This plan changes the supported command path, not the operating-system trust model.
- Use bounded parent-direct implementation because the scope includes workflow and validation authority. Before implementation, obtain design approval, publish the active plan, initialize its own permitted ledger and review route, and retain ordinary review and stop limits.
