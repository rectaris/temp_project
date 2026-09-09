# Restore the large Python test baseline and CI coverage

status: checked
primary_invariant: the current one-correction execution contract is tested without stale expectations, and each previously omitted large root Python suite runs in CI without weakening existing validation
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"At HEAD 3c9b47c, python3 tests/test-sandboxed-plan-worker.py runs 96 tests and fails only two cases; both reach a second correction after the execution state has already stopped for restructuring."}
  - {"kind":"existing_mechanism","evidence":"AGENTS.md, MAX_CORRECTIONS = INDEPENDENT_REVIEW_LIMIT - 1, and test_one_rejected_correction_stops_and_replay_is_rejected independently establish the current one-correction limit."}
  - {"kind":"bounded_prototype","evidence":"Existing fake-Codex helpers accept the same availability-state and orchestration-run-id arguments for an initial run and a correction, so reuse can be tested within the one permitted correction."}
  - {"kind":"existing_mechanism","evidence":"The separate copier-fixture-validator CI job already demonstrates a root-only parallel job that checks out the repository, sets up Python 3.12, and runs one complete unittest entrypoint."}
completion_conditions:
  - The complete sandboxed plan worker suite passes while proving that one correction is accepted, a second correction is refused before worker output, and the source repository remains unchanged.
  - The availability-state regression reuses one orchestration run across the initial attempt and its single permitted correction, skips the known-unavailable preferred model, and separately preserves run-id mismatch and non-availability failure coverage.
  - The complete plan restructuring suite passes unchanged before its later structural split is considered.
  - The complete plan execution state suite passes unchanged before its later structural split is considered.
  - CI contains separate jobs for the plan restructuring, plan execution state, and sandboxed plan worker suites, each running its existing complete-suite command without serializing the validate job or removing an existing job or step.
  - Deterministic validation-tool tests fail when any of the three CI jobs or fixed commands is absent and continue to protect the pre-existing CI requirements.
completion_witness_map:
  - {"condition_sha256":"sha256:f597659a50b0ec4c91c7d478e2fa91003e6c37c0ab40f0f1abc4a140a75375b9","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:beedb2be6d325164af2c41e368f2bac2d62c0a562bfec3c7318a10c4cd31ace3","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:864af082c313874020947b7e05d16e3ba31623a4f950a3609e7d26530b3cab6c","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:665f1b726cc07c77d826ae9497e9c573f100b2fb31378e29680dca4fa2b5a51d","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:3361c4ccb5cfcf1a1cfa1ab03c6268272cd565ae6b2c70698cf88cfd3b2740b4","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:40f68025106032747dc2ea7bbefe5b0a76f1b7726e6bc6a375a7711d673ba546","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - .github/workflows/ci.yml
  - tests/test-sandboxed-plan-worker.py
  - tests/validation_tools/generated.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/checked/2026/09/01-15/267-modularize-change-aware-copier-validator-tests.md
  - scripts/plan-execution-state.py
  - scripts/run-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
  - tests/test-plan-restructure.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-validation-tools.py
  - tests/validation_tools/generated.py
  - .github/workflows/ci.yml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-plan-restructure.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/plan_validation_commands.py --self-test
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Align only stale sandbox test scenarios with the current one-correction budget; do not change production scripts or weaken coverage of correction lineage, availability-state reuse, run identity, fallback classification, refusal before worker start, and source cleanliness.
  - Add independent CI jobs for the three previously omitted large root Python suites and deterministic checks for those jobs, while preserving every existing CI job and validation step.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:021d6ff00b50f565676484bb8696f0d6691052b5338623e3344905b0a9708dd3","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:5a7ca083cd36775efdcdcb1f877d27351c14527797c1839b58faf419ff391d54","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - keep MAX_CORRECTION_ROUNDS, MAX_CORRECTIONS, execution-state transitions, runner production code, and the one-correction safety boundary unchanged
  - rewrite the correction-lineage regression to accept exactly round 1 and reject round 2 before any second-correction worker output is created; retain the unchanged-source assertion
  - exercise availability-state reuse from an initial fake-Codex attempt into its one permitted correction under one orchestration run; test run-id mismatch and non-availability failure from fresh eligible states rather than from an already exhausted correction lineage
  - add one independent GitHub Actions job per complete-suite command; do not add needs edges to the validate job or combine the suites into a serial job
  - preserve the validate, copier-fixture-validator, and minimum-compatibility jobs and every existing step, trigger, permission, environment requirement, and command
  - keep all CI additions root-only because these suites validate this template repository and are not generated-project commands
  - add deterministic GeneratedCiTest assertions for exact job identifiers and fixed commands, including assertions that the three commands are outside the validate job
  - do not move or split any test module in this plan; after this plan is checked, assess and admit separate plans for test-plan-restructure.py, test-plan-execution-state.py, test-sandboxed-plan-worker.py, copier_fixture_validator/grammar.py, and validation_tools/plan.py
  - use bounded parent implementation because the write scope changes validation authority; require an independent read-only review before authoritative validation
checked_summary_ja: sandbox worker の訂正回数テストを現行の 1 回上限へ合わせ、CI で未実行だった 3 個の大規模 Python テストスイートを独立ジョブとして常時実行する。

## Decisions

- After the initial candidate and one isolated correction, another correction attempt is refused and the execution state is replan_required.
- Two tests in tests/test-sandboxed-plan-worker.py attempt a second correction and fail before the expected assertions because the current execution state has already stopped for restructuring.
- The commands python3 tests/test-plan-restructure.py, python3 tests/test-plan-execution-state.py, and python3 tests/test-sandboxed-plan-worker.py are accepted validation commands but are not executed by the current GitHub Actions workflow.
- Plan 268 changes only the stale sandbox worker test expectations, CI job declarations, and deterministic tests of those declarations; it does not move test modules.
- After Plan 268 is checked, each remaining large Python test target is evaluated and, when still justified, receives a separate implementation plan with its own inventory-preservation witness.
- Preserve each behavior formerly embedded after the second correction by moving it into an eligible initial-plus-one-correction sequence or a fresh repository execution state.
- Test the root CI job contract in `GeneratedCiTest`; do not mirror root repository CI into the generated template.
- Do not reserve successor plan identifiers. Reassess the identified targets after this plan is checked so later plans use the resulting green baseline and current repository state.

## Tasks

- [x] Record the two sandbox worker failure identities and confirm that no other test in the complete suite fails at the activation baseline.
- [x] Change the correction-lineage scenario to accept one correction and reject the next correction before worker execution, while retaining lineage, output, and source-cleanliness assertions.
- [x] Change the availability-state scenario to reuse state between the initial attempt and the single permitted correction, then preserve run mismatch and semantic-failure coverage in fresh eligible execution states.
- [x] Add three independent root CI jobs that run the existing complete commands for plan restructuring, plan execution state, and sandboxed plan worker behavior.
- [x] Extend `GeneratedCiTest` to require the new job identifiers and commands, prove that they are not appended to `validate`, and continue checking the existing jobs and commands.
- [x] Run every focused validation command and obtain an independent read-only review with no unresolved High or Medium finding.
- [x] Run the authoritative validation suite exactly once for an otherwise accepted change, then archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Activation evidence: `python3 tests/test-plan-restructure.py` passes 177 tests in 97.372 seconds; `python3 tests/test-plan-execution-state.py` passes 76 tests in 80.834 seconds; `python3 tests/test-sandboxed-plan-worker.py` runs 96 tests in 57.494 seconds and fails only `test_correction_lineage_allows_two_rounds_and_rejects_third` and `test_correction_reuses_same_run_availability_and_only_falls_back_for_availability`.
- The failing sandbox tests both attempt a second correction. `scripts/plan-execution-state.py` and its regression tests establish one permitted correction followed by `replan_required`, matching the current root policy.
- The full decision comparison remains local under `.agent-artifacts/decision-audits/`; this plan records only the accepted implementation decisions.
- Implementation evidence: the sandboxed plan worker suite passes 97 tests, up from 96 run and 2 failed, because the stale second-correction expectations were replaced by one accepted correction, one refused correction, and a separate correction-path availability classification regression.
- Focused validation at the final state: `python3 tests/test-sandboxed-plan-worker.py` 97 OK; `python3 tests/test-plan-restructure.py` 177 OK; `python3 tests/test-plan-execution-state.py` 76 OK; `python3 tests/test-validation-tools.py` 81 OK; `python3 scripts/plan_validation_commands.py --self-test`, `python3 scripts/check-copier-template.py`, `python3 scripts/check-yaml.py .`, pinned actionlint with shellcheck, and `git diff --check` all pass.
- Independent read-only review ran twice. The first round reported one Medium finding for lost correction-path availability classification coverage and three Low findings. One parent-direct remediation round added `test_correction_classifies_unavailable_preferred_model_and_records_fallback`, replaced the unreachable mismatch assertion with an output-directory absence assertion, anchored the non-availability failure message on its full prefix, and aligned the CI bubblewrap probe with `ensure_bwrap_usable`. The second round reported no High, Medium, or Low finding.
- Authoritative validation ran once after the review cleared: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` both pass.
- CI additions stay root-only. `plan-restructure`, `plan-execution-state`, and `sandboxed-plan-worker` are independent jobs with no `needs` edge, and every existing job, step, trigger, and permission is unchanged.
