# Enforce bounded Python lint through an isolated pinned entrypoint

status: in_progress
implementation_mode: parent_direct
primary_invariant: The same pinned Python lint rules reject selected defects in root and managed template scripts through an isolated entrypoint, without expanding automatic writes into project-owned files.
replan_sources:
  - docs/plan/active/364-enforce-bounded-python-lint.md
replan_contract: docs/plan/replanned/contracts/364-enforce-bounded-python-lint.json
integration_gates:
  - This plan proves every acceptance item of plan 364 together, because the installed lint entrypoint is the only witness that the resolved undefined-name diagnostics leave the initial scope clean.
successor_plans:
  - docs/plan/active/353-enforce-bounded-python-lint.md
inherited_acceptance_digests:
  - sha256:a3a0b337ed66d64d66bde9dfac65dc46f5481a88bb30c51691b81d0e18e92be0
  - sha256:45d0a5a440d4225c2c9a0c49c23a13226a3cee80c8fbdced266eedf625c400fc
integration_source_ids:
  - 364
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
  - {"evidence":"The reviewed plan-364 candidate sha256:d1f362c4961a81b800d02c01f1c9be4fb567a6b603ed1e69ab44a97dbee285e8 applies cleanly at source 09e6cfe. It adds the pinned requirements, ruff.toml, mirrored lint-python.py and a 426-line real-tool test module.","kind":"bounded_prototype"}
  - {"evidence":"With a PYTHONPATH sitecustomize that calls os._exit(0), python3 scripts/lint-python.py returned 0 without running Ruff, while python3 -I scripts/lint-python.py ran the real check under the same environment.","kind":"reproduced_defect"}
  - {"evidence":"is_python_script_check in scripts/plan_validation_commands.py matches only (python3, script, *args), so an isolated declarable form needs its own bounded checker rather than an optional flag on every allowlisted script.","kind":"existing_mechanism"}
  - {"evidence":"Root required lint, generated project-agent-workflow.yml, the paired validate-changes.py selectors, and copier_inventory.py already expose command registration, managed scope selection and mirrored-tool validation.","kind":"existing_mechanism"}
completion_conditions:
  - Required root and generated workflow checks run Ruff 0.15.7 with E9,F541,F631,F634,F821,F822,F823 on the documented Python scope and fail on findings, missing tools, wrong versions or invalid configuration.
  - Every required caller launches the wrapper in isolated mode, so an inherited PYTHONPATH sitecustomize cannot make the lint check report success without running Ruff.
  - Check mode changes no source bytes; explicit fix mode requires the task worktree, permits only F541 safe fixes and refuses targets outside its declared scope before writing.
  - Root and generated lint entrypoints, pinned settings and documented rule behavior are registered and mechanically checked for the intended counterpart relationship.
  - A real Copier update installs the managed lint additions while preserving existing product code, product dependency manifests, project-owned policy/configuration and previously required validation.
  - The observed undefined-name diagnostics are resolved in their source files and the entire initial lint scope passes without broad ignores or lost behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:77f2e875994d44e455a12b2268c174119fb5a1acf12770550b9a786dc752a181","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f0b8b6dc70f2a53463ff2145ccc9b292409208d33677bcae617033db389c4ba4","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:919bfca12afbe154671cb837a2b0a01d6fac56c9e4e3ae3167c2d2e547cf514f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ecc66ab3be18b49848e2b9b86c98664ce1ff62f1079bb66c9b58d27de9a3e3e3","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:617f8fbba06dd0b060666ffe2fac5ead333a640715462306f0fb0ea6e2c2b38b","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:1a400302a98c26978ac92a12b38b63919957a3502d5ad94bd7f2e0d305faf367","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - pyproject.toml
  - uv.lock
  - tools/python-quality/requirements.txt
  - template/.project-agent-workflow/tools/python-quality/requirements.txt
  - tools/python-quality/ruff.toml
  - template/.project-agent-workflow/tools/python-quality/ruff.toml
  - scripts/lint-python.py
  - template/.project-agent-workflow/scripts/lint-python.py
  - scripts/lint-project-workflow.sh
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
  - tests/validation_tools/python_lint.py
  - tests/validation_tools/changes.py
  - tests/validation_tools/generated.py
  - tests/validation_tools/plan.py
  - references/validation.md
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-execution-state.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A contributor receives additional Python correctness diagnostics locally and in CI, with identical pinned rules and only explicitly permitted automatic fixes in the task scope.
  - The initial lint check passes because the existing undefined-name diagnostics are resolved with their original intended behavior preserved, rather than hidden by exclusions.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a3a0b337ed66d64d66bde9dfac65dc46f5481a88bb30c51691b81d0e18e92be0","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:45d0a5a440d4225c2c9a0c49c23a13226a3cee80c8fbdced266eedf625c400fc","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: Pythonの未定義名などを隔離起動の検査で拒否し、自動修正を許可した規則に限定する。

## Decisions

- Owner instruction on 2026-09-16: implement plan 364. Plan 364 had spent its cumulative four reviews and stopped at `replan_required`, so that instruction is recorded as the schema-4 `owner_continuation_authorization` of this reconstruction instead of reopening the stopped run.
- Keep one successor. The second acceptance item can only be witnessed by running the lint entrypoint the first item installs, so the two items share one witness and cannot be accepted separately.
- Reuse the reviewed plan-364 candidate bytes as the implementation baseline. Every accepted plan-364 decision below is retained unchanged; this plan changes only the launch method and its declarable command form.
- Pin Ruff 0.15.7 in the root development dependency and paired tools/python-quality/requirements.txt files. Keep configuration in tools/python-quality/ruff.toml and its managed counterpart; verify pin parity.
- Inspect Python under scripts/, tests/ and template/.project-agent-workflow/scripts/ at root; inspect only .project-agent-workflow/scripts/ in generated projects. Exclude caches and reject symlink escapes; never auto-discover downstream product directories.
- Enable exactly E9,F541,F631,F634,F821,F822,F823 with preview disabled. Automatic lint fixes allow F541 only with unsafe fixes disabled; other findings require reviewed code changes.
- Add paired scripts/lint-python.py. Checking is the default; --fix requires a live task worktree, explicit file operands and whole-request checks against the lint target/rule allowlists. Never implicitly fix the complete scan scope or fetch tools.
- Launch that wrapper as `python3 -I` from the root lint runner, the generated CI job and both change-aware selectors. Isolated mode drops PYTHONPATH, the script directory and user site, so a `sitecustomize` module can no longer exit successfully before Ruff selection. The wrapper imports only the standard library, so isolation costs it nothing.
- Admit the isolated form through its own bounded allowlist entry rather than making `-I` optional for every allowlisted script, so the weaker spelling of this entrypoint stays undeclarable.
- Keep downstream product dependencies and configuration intact. Install the pinned managed Ruff requirements explicitly in generated CI; document local setup and fail clearly when the tool is missing.
- Admit only the check invocation in plan validation and change-aware selectors. Never admit --fix as a validation command. Preserve all existing commands and CI jobs.
- Treat the guarded digest reference and missing annotation imports as diagnostics to resolve from source evidence, not proof of 13 runtime failures. Do not format whole files in this plan.
- The guard proves worktree ownership, not a direct task's per-file authority. The caller retains responsibility for task write-scope compliance; explicit operands and fixed tool target/rule lists bound the tool's writes.
- Isolating the other required Python launch points is a separate pre-existing repository property and stays outside this plan.

## Tasks

- [ ] Apply the reviewed plan-364 candidate bytes as the implementation baseline and confirm the resolved undefined-name references keep their intended binding, including the guarded EMPTY_CHAIN_DIGEST initializer value.
- [ ] Launch the wrapper in isolated mode from scripts/lint-project-workflow.sh, the generated CI job and both change-aware selectors, and admit only that isolated form in both plan validation allowlists.
- [ ] Extend the real-tool test module with a `sitecustomize` case proving the non-isolated launch is defeated and the isolated launch still runs Ruff, and cover the isolated selector emission and allowlist decisions.
- [ ] Keep the existing real-tool coverage for every selected rule, missing and mismatched tool versions, invalid configuration, nonempty target selection, path escapes, failed preflight with no partial writes, fix idempotence and preservation of project-owned files.
- [ ] Run the real check against the complete current initial scope in the focused suite. Do not substitute fake tool output or skip tests when Ruff is missing.
- [ ] Keep every new file and mirrored parity registered in copier_inventory.py and check-copier-template.py, and keep root and generated validation guidance and generated-CI assertions aligned with the isolated launch.
- [ ] Extend the update-source fixture inventory and real Copier-update scenarios for the new managed files; assert project-owned byte preservation and existing validation retention. Read the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite.
- [ ] Review and validate the final in-scope diff, then commit the lint implementation independently of later type-checking and formatter changes and use the ordinary completion and publication lifecycle.

## Validation Notes

- Plan 364 stopped at `replan_required` with `parent_remediation_budget_exhausted` after its epoch-3 review reported one Medium finding, and all four cumulative reviews were spent. This plan is its owner-authorized reconstruction, not a reopening of that run; all three stopped ledgers stay byte-identical.
- The reconstruction changes only the launch method, the declarable command form and the matching tests. The source requirements, accepted safety conditions and both acceptance items are preserved exactly.
- The epoch-2 Medium finding remains fixed in the inherited baseline: `ruff_executable()` resolves the pinned tool through `sysconfig.get_path("scripts")` and invokes it directly, so a working-directory `ruff.py`, a `PYTHONPATH` `ruff` package and an earlier `PATH` `ruff` cannot replace it.
- Ruff 0.15.7 must be installed into the repository Python environment from tools/python-quality/requirements.txt before the focused suite runs; the real-tool tests must never be skipped when the tool is missing.
