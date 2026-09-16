# Admit only the unused fourth review through a separately authorized immutable continuation

status: checked
primary_invariant: An explicitly authorized fourth-review continuation proves exactly three prior formal reviews and admits only one remaining review, without rewriting stopped histories or increasing the cumulative maximum of four.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At b2b7ab6, continue_final_state and continue_state already enforce private non-aliased paths, canonical predecessors, owner authorization, source adoption, both registries, atomic one-child consumption and exact recovery. A new explicit route can reuse that envelope.","kind":"existing_mechanism"}
  - {"evidence":"validate_execution_epoch, validate_state and record_event already enforce schema-specific terminal bounds and cumulative review accounting. Schema 3 can retain the schema-2 field set while requiring epoch 3 and exactly three predecessor reviews.","kind":"existing_mechanism"}
  - {"evidence":"final_continuation_fixture(origin_reviews=1), staged_parent_review_fixture and existing root/generated CLI tests can build a stopped three-review history and exercise a fourth-review route without any production ledger or product write.","kind":"existing_mechanism"}
  - {"evidence":"Plan 364's canonical stopped epoch-2 ledger records two prior formal reviews and one local review. Its candidate and all three stopped ledgers are retained; the current execution gate refuses further work, matching the existing policy rather than a runtime defect.","kind":"existing_mechanism"}
completion_conditions:
  - A new continue-fourth-review operation admits only an ungrouped parent-direct epoch-2 stop for parent_remediation_budget_exhausted, with exactly one verified formal review in each of its canonical epoch-0, epoch-1 and epoch-2 records.
  - Admission binds all three unchanged stopped histories, both continuation edges, each prior reviewer admission, existing registry identities, exact plan and invariant, bounded owner authorization and the selected descendant source with unchanged committed plan bytes.
  - The fresh schema-3 epoch-3 child permits at most one correction and one formal review within the unchanged cumulative maximum of four; recording and history reading reject a fifth review and every existing continuation route rejects a further child.
  - Historical schemas and ordinary/final routes retain their existing behavior, and the new operation preserves path, lock, private-file, occupied-destination, exact-recovery, replay and concurrent-fork refusals before unauthorized effects.
  - Root and generated guidance distinguish the new individually authorized fourth-review route from unchanged historical routes and preserve independent review, adversarial preflight, validation, source adoption and parent-only publication authority.
completion_witness_map:
  - {"condition_sha256":"sha256:8b3aeb3e6b7885959f439a7a836afeaf5961687c26ef253982f719472bb2c390","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:58a0fc331392a8eafd2517e50d36d96e20194cb529c59e4c742eb86b413c0c96","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:82a15786c81025715d9ce2a12fa40663ead8b841f396c22486f0ae7f0e0d8efe","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:c805603f1df15a9a4dba42159ead510aab76e9522653264d86cc6afc00d99e57","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:97e6febce8188a6e4853db826726da6ac9f64ee343b09e5c7758cbb800e23b24","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - AGENTS.md
  - template/AGENTS.md.jinja
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
required_specs:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An owner can explicitly authorize the unused fourth review after a verified three-review stopped history, while all stopped evidence, source and registry bindings, mandatory acceptance gates and the cumulative four-review limit remain intact.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:22d8b2e6b65188488b227bc9cacb326e10ed9cd0f17bf1aea3757c9e47d9e2ec","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
checked_summary_ja: 停止済みの記録を保ったまま、未使用の第4回レビューだけを個別承認で認める。

## Decisions

- On 2026-09-16 the owner answered true to the explicit question titled 未使用の1回を使うための限定的な規則変更を含め、364の継続を承認する. The approval preserves stopped histories, the cumulative maximum of four and existing acceptance conditions.
- Use bounded parent-direct implementation in a separate execution ledger. Publish this policy before plan 364 adopts it, and preserve all ordinary route, independent-review, preflight and authoritative-validation requirements.
- Add continue-fourth-review rather than widening continue or continue-final. Reuse the final-continuation path/lock/registry/publication envelope and require explicit epoch-zero and epoch-one ancestor paths in addition to the stopped epoch-two predecessor.
- Use schema 3 for the new authorization and execution epoch, retaining the schema-2 field set with epoch 3, predecessor_review_count 3 and cumulative limit 4. Reject old authorization schemas on the new route and preserve exact historical schema semantics.
- Verify canonical epoch 0, 1 and 2 records, each with one formal review and the same plan, invariant and parent-direct mode. Bind each predecessor digest, event leaf, source relationship and registered continuation edge; verify every review against the supplied existing reviewer-registry prefix.
- Reuse the existing exact descendant-source adoption checks and one-time predecessor-genesis consumption. Do not overwrite predecessor records, create replacement registries, allow workers, omit ancestor path checks, or permit a second child.
- Enforce the final single-review bound in both recording and stored-history validation. Epoch 3 grants no further continuation and no fifth cumulative review, even if a caller supplies another owner quotation or a new state path.
- Extend isolated real CLI fixtures for both layouts, positive source adoption, omitted or changed ancestors, incorrect review counts, old authorization schemas, registry omissions, unsafe paths, occupied destinations, exact recovery, forks and exhaustion. Retain all existing regressions.
- Temporarily defer the unbound direct root plan 364 through this separate authoring lifecycle only. Preserve every non-lifecycle byte and restore its exact original active-plan bytes after this policy is checked and published; this restoration authorization does not waive the new continuation gate.
- Do not change plan 342, unrelated backlog plans, plan 364's product candidate, its acceptance, or any existing stopped execution record in this implementation.

## Tasks

- [x] Implement the explicit fourth-review route and schema-3 bounds using the existing guarded final-continuation envelope.
- [x] Verify the complete three-ledger ancestry and both registry histories before any new child is consumed or published.
- [x] Apply strict one-review and cumulative-four limits at record and history-read boundaries while preserving historical behavior.
- [x] Extend the existing root/generated isolated CLI fixture coverage for admission, all new refusal paths and unchanged earlier routes.
- [x] Align root and generated workflow, orchestration and entrypoint policy with the new explicit operation.
- [x] Review the exact candidate independently, run focused checks and the authoritative suite once, commit and publish the accepted policy before any plan-364 product correction.

## Validation Notes

- The plan-364 candidate remains sha256:a60254482ab68117191c69e3ca072066376874b0601886051e081fcd76940923. Its stopped epoch-2 ledger remains sha256:0d9ee322de2c6299c5ca87283e0350e4be92356afe844235a657b96379fc4661. These observations do not grant product write or acceptance authority.
- The current policy intentionally rejects a fourth review after epoch 2. This plan changes that rule only under the new explicit owner approval; it does not retroactively claim the previous stop was erroneous.
- Plan 364 must separately adopt the published policy, receive its exact new owner-bound continuation, resolve the Ruff execution assumptions and pass its remaining review and unchanged validation.
- Implemented at 86cda16 on the task worktree for this plan. `python3 tests/test-plan-execution-state.py` passed 212 tests, and `python3 scripts/check-copier-template.py` reported the static template check passed. Root and generated `plan-execution-state.py` remain byte-identical.
- One independent review of the exact candidate reported no significant issues. It probed the cumulative bound at both the record and stored-history boundaries, the refusal of any epoch-3 continuation through `continue`, `continue-final` and `continue-fourth-review`, the path, alias and lock coverage of `--epoch-one-state`, the behavior-preserving `edges` and recovery refactors, and the two-way authorization schema gating. All three stopped ledger files stayed byte-identical across every probe.
- The authoritative suite ran once on the accepted candidate: `scripts/lint-project-workflow.sh` reported the workflow package lint passed and `tests/smoke.sh` reported the smoke test passed.
- `AGENTS.md` first exceeded the routed-entrypoint byte budget at 22875 bytes. The two duplicated detail clauses were shortened, not dropped: the full recovery-refusal rule remains in `docs/agent/SPEC_PLAN_WORKFLOW.md`, `references/orchestration.md` and the generated counterparts. The reviewed entrypoint is 22713 bytes. A second bounded review of that delta reported no significant issues.
