# Modularize and select Copier fixture validator tests

status: in_progress
primary_invariant: every existing Copier fixture validator test remains reachable exactly once through the unchanged complete-suite command, while Git-visible changes may select only an explicitly mapped nonempty domain subset and every shared or unclassified relevant change falls back to that complete suite
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"At HEAD 8aa7e3f, tests/test-copier-fixture-validator.py has 6,918 lines and 563 tests; its complete run passes in 194.640 seconds, while module import takes 0.087 seconds, one test takes 0.088 seconds, and one five-test class takes 0.449 seconds."}
  - {"kind":"existing_mechanism","evidence":"tests/hooks and tests/validation_tools already keep compatibility entrypoints while importing directly executable non-discovery domain modules exactly once; checked Plan 085 records the successful extraction and inventory method."}
  - {"kind":"existing_mechanism","evidence":"scripts/validate-changes.py already collects staged, unstaged, and untracked Git paths and emits inspectable JSON, while scripts/plan_validation_commands.py already validates fixed test argv without shell execution."}
completion_conditions:
  - The existing python3 tests/test-copier-fixture-validator.py command discovers and runs exactly the activation-baseline test-method inventory once, with no missing, added, or duplicate inherited case after extraction.
  - Each extracted domain module is directly executable, owns only its assigned test classes, imports shared fixtures explicitly from support.py, and generic discovery does not execute the aggregate inventory twice.
  - A Git-visible change confined to one extracted domain module selects a nonempty strict subset of the complete inventory, while a shared support, aggregate entrypoint, selector, allowlist, production parser or validator, or unclassified relevant path selects the complete-suite command.
  - The selector emits only fixed repository-owned argv accepted by plan_validation_commands.py, never derives executable text from a changed path or file content, and exits nonzero without running tests when its Git query or command validation fails.
  - The new Python files are covered by the deterministic source inventory and compilation checks, and CI runs the unchanged complete-suite entrypoint in a separate job without replacing the existing lint, smoke, Hook, Copier update, or compatibility steps.
completion_witness_map:
  - {"condition_sha256":"sha256:39a5befe5a153033c6d8b97dbed45e7b986039faa1e5ebb0ee817aa7294cd7cf","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:139d9f0f464b68105c4a8f1768af553dbea537f69431fe1dc79bbfebf376e6b7","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:8bb5b6bfdf88d1e9bc9e249f2b6bbf6a4eca652f552b13b065713d9defb6ccc3","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:525f63bb0a078172380980847d5cb5fc30073a13a3feb91a91180ecb74b7aa6e","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2467f5b65e8a539e3aec7a71e32512a05f0d418b4c42133b74c69edca41f821d","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - .github/workflows/ci.yml
  - scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - tests/AGENTS.md
  - tests/test-copier-fixture-validator.py
  - tests/select-copier-fixture-validator-tests.py
  - tests/copier_fixture_validator/__init__.py
  - tests/copier_fixture_validator/support.py
  - tests/copier_fixture_validator/contract.py
  - tests/copier_fixture_validator/inventory.py
  - tests/copier_fixture_validator/execution.py
  - tests/copier_fixture_validator/grammar.py
  - tests/copier_fixture_validator/placement.py
  - tests/validation_tools/changes.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/checked/2026/08/01-15/085-ai-test-modularization.md
  - tests/AGENTS.md
  - tests/test-copier-fixture-validator.py
  - scripts/validate-changes.py
  - scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - .github/workflows/ci.yml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/plan_validation_commands.py --self-test
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Extract every existing copier fixture validator unittest class into the declared responsibility modules while preserving the exact complete-suite command, inherited method inventory, fixtures, behavior, and exit status.
  - Add a root-only Git-change selector that runs a directly affected domain subset but falls back to the complete suite for shared or unclassified relevant changes, and retain complete validation in CI and before plan completion.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:66a58e1b1041369716100ce0c83ee77ca2d6fecf6479afd82f18cf79f0f7f81c","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"acceptance_sha256":"sha256:b8477b75f93aed44f167713153c03e68a0e2f4e06724d3e48dc8b980cf3bd3a9","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - record the activation-baseline unittest id inventory before extraction and require exact equality with the aggregate post-extraction inventory; moving tests must not add, delete, rename, skip, xfail, or duplicate an inherited case
  - keep tests/test-copier-fixture-validator.py as the unchanged complete-suite command path and make every extracted domain module directly executable without a test-prefixed filename that generic discovery would execute twice
  - build selected commands only from a static changed-path mapping and validate each argv through scripts/plan_validation_commands.py; never interpolate a changed path, diff content, environment value, or repository file content into an executable command
  - select the aggregate complete-suite command for changes to shared support, the aggregate entrypoint, the selector, its allowlist or tests, scripts/project_workflow/copier_fixture_validator.py, any supporting shell parser module, and every unclassified path inside the declared relevant boundaries
  - keep scripts/validate-changes.py and its generated-project counterpart unchanged; tests/select-copier-fixture-validator-tests.py is a root-only test-development entrypoint and does not add generated-project behavior
  - add the aggregate command to a separate CI job so its runtime does not serialize the existing validate job, and do not remove, weaken, reorder, or conditionally skip any existing CI validation step
  - keep per-class timing descriptive only; accept performance through a deterministic nonempty strict-subset inventory for a domain-only change, not through a wall-clock threshold
checked_summary_ja: Copier fixture validator の既存テストを責務別モジュールへ分割し、共有または未分類の変更では全件へ戻る Git 変更選択入口を追加して、全件検証を維持する。

## Decisions

- tests/test-copier-fixture-validator.py remains executable and imports every extracted unittest class exactly once.
- Existing unittest classes move without behavioral edits into tests/copier_fixture_validator/contract.py, inventory.py, execution.py, grammar.py, and placement.py; __init__.py and support.py provide package and shared support boundaries.
- Put shared constants, fixture source text, helpers, and the inherited `ContractSupportTest` base in `tests/copier_fixture_validator/support.py`; it contains no independently discovered test method.
- Place behavior classes into the five domain modules according to their existing responsibility and source order. Each class has exactly one owning module, and each module remains directly executable with `unittest.main()`.
- Use non-`test` module names under `tests/copier_fixture_validator/` so generic test discovery reaches the cases only through the compatibility entrypoint.
- tests/select-copier-fixture-validator-tests.py is the root-only executable that maps Git-visible changed paths to fixed copier-fixture-validator test commands.
- Match the staged-first, `--all`, `--staged`, `--print-only`, and `--json` inspection behavior already used by `scripts/validate-changes.py`, but keep the two command interfaces separate.
- A registered changed path selects its declared test-module commands, while a shared implementation path or an unregistered relevant path selects the complete-suite entrypoint.
- Repository-required lint and smoke commands and the existing complete test entrypoint remain required after focused commands pass.
- For a changed extracted domain module, the selected test inventory is a nonempty strict subset of the 563-case complete inventory, and unknown or shared paths never select an empty set.
- Treat a domain-module-only change as eligible for that module command. Treat `support.py`, `__init__.py`, the aggregate entrypoint, the selector and its validation files, the production validator, `shell_lexical.py`, `shell_functions.py`, `shell_execution.py`, and an unknown path under those test or implementation boundaries as requiring the aggregate command. An unrelated path may report that no matching Copier fixture validator test is required.
- Add only literal selector and domain-module argv to the root plan validation allowlist. Reject flags, absolute paths, parent traversal, shell metacharacters, duplicate commands, Git-query failure, and any command derived from changed content.
- Add a separate root CI job that executes `python3 tests/test-copier-fixture-validator.py`. Do not install the selector or the root test modules into generated projects.
- Use bounded parent implementation because the write scope changes validation authority and includes paths the writable plan runner must not edit. Require one independent read-only review before authoritative validation.
- Leave `test-plan-restructure.py`, `test-sandboxed-plan-worker.py`, `test-plan-execution-state.py`, `smoke.sh`, and `copier-update.sh` structurally unchanged in this plan. Use the accepted module and selection pattern as evidence for a later separately authorized plan rather than widening this one.

## Tasks

- [ ] Capture the activation-baseline unittest ids, count, exit status, and per-class timings for the existing aggregate command without changing test behavior.
- [ ] Move shared fixtures and helpers into `support.py`, then move every existing test class into exactly one declared domain module using explicit imports and no wildcard dependency.
- [ ] Replace the original file body with the compatibility imports and aggregate `unittest.main()` entrypoint, and prove that the pre- and post-extraction unittest id inventories are identical.
- [ ] Implement the root-only changed-path selector with static argv, staged/all modes, print-only and JSON reports, conservative relevant-path fallback, and fail-closed Git and command-validation behavior.
- [ ] Add validation-tool tests for exact domain selection, shared and unknown relevant fallback, unrelated paths, staged precedence, command deduplication, JSON output, unsafe input rejection, Git failure, direct module execution, and exact aggregate inventory preservation.
- [ ] Add the new sources and executable commands to the root inventory and command allowlist, document the focused editing command in `tests/AGENTS.md`, and add the complete aggregate command as a separate CI job.
- [ ] Run focused validation and one independent read-only review with zero unresolved High or Medium findings.
- [ ] Run the authoritative validation suite exactly once for an otherwise accepted change, then archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending implementation.
