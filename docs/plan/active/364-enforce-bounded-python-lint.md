# Enforce bounded Python lint with explicitly permitted automatic fixes

status: deferred
completion_deferred_reason: Await the separately owner-approved unused-fourth-review policy; preserve the candidate and all stopped ledgers, then restore the exact original plan before gated continuation.
implementation_mode: parent_direct
primary_invariant: The same pinned Python lint rules reject selected defects in root and managed template scripts without expanding automatic writes into project-owned files.
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
  - {"evidence":"At source b1c909a, Ruff 0.15.7 with E9,F541,F631,F634,F821,F822,F823 scanned scripts, tests and template/.project-agent-workflow/scripts and reported 13 F821 diagnostics in five files; no other selected rule failed.","kind":"bounded_prototype"}
  - {"evidence":"The same source with F,B produced 184 diagnostics across seven rules. The initial rule list is explicit; this plan does not admit the wider rules or imply full Python bug coverage.","kind":"bounded_prototype"}
  - {"evidence":"Root required lint, generated project-agent-workflow.yml, the paired validate-changes.py selectors, and copier_inventory.py already expose command registration, managed scope selection and mirrored-tool validation.","kind":"existing_mechanism"}
completion_conditions:
  - Required root and generated workflow checks run Ruff 0.15.7 with E9,F541,F631,F634,F821,F822,F823 on the documented Python scope and fail on findings, missing tools, wrong versions or invalid configuration.
  - Check mode changes no source bytes; explicit fix mode requires the task worktree, permits only F541 safe fixes and refuses targets outside its declared scope before writing.
  - Root and generated lint entrypoints, pinned settings and documented rule behavior are registered and mechanically checked for the intended counterpart relationship.
  - A real Copier update installs the managed lint additions while preserving existing product code, product dependency manifests, project-owned policy/configuration and previously required validation.
  - The 13 observed F821 diagnostics are resolved in their five source files and the entire initial lint scope passes without broad ignores or lost behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:77f2e875994d44e455a12b2268c174119fb5a1acf12770550b9a786dc752a181","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:919bfca12afbe154671cb837a2b0a01d6fac56c9e4e3ae3167c2d2e547cf514f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ecc66ab3be18b49848e2b9b86c98664ce1ff62f1079bb66c9b58d27de9a3e3e3","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:617f8fbba06dd0b060666ffe2fac5ead333a640715462306f0fb0ea6e2c2b38b","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:07d10fa6489cdee447abb73738153242b92e8b19eff86747e3371191d8eb7c57","witness":"python3 tests/test-validation-tools.py"}
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
checked_summary_ja: Pythonの未定義名などを検査し、自動修正を許可した規則に限定する。

## Decisions

- Owner instruction: create implementation plans for stronger static checks, restricted automatic fixes and separate formatting changes. Keep this plan unstarted in backlog until implementation is requested.
- Execute this plan first. Use parent-owned implementation for dependency, validation-authority and guarded-write changes; retain independent review, focused checks and the full authoritative suite.
- Pin Ruff 0.15.7 in the root development dependency and paired tools/python-quality/requirements.txt files. Keep configuration in tools/python-quality/ruff.toml and its managed counterpart; verify pin parity.
- Inspect Python under scripts/, tests/ and template/.project-agent-workflow/scripts/ at root; inspect only .project-agent-workflow/scripts/ in generated projects. Exclude caches and reject symlink escapes; never auto-discover downstream product directories.
- Enable exactly E9,F541,F631,F634,F821,F822,F823 with preview disabled. Automatic lint fixes allow F541 only with unsafe fixes disabled; other findings require reviewed code changes.
- Add paired scripts/lint-python.py. Checking is the default; --fix requires a live task worktree, explicit file operands and whole-request checks against the lint target/rule allowlists. Never implicitly fix the complete scan scope or fetch tools.
- Keep downstream product dependencies and configuration intact. Install the pinned managed Ruff requirements explicitly in generated CI; document local setup and fail clearly when the tool is missing.
- Admit only the check invocation in plan validation and change-aware selectors. Never admit --fix as a validation command. Preserve all existing commands and CI jobs.
- Treat the guarded digest reference and missing annotation imports as diagnostics to resolve from source evidence, not proof of 13 runtime failures. Do not format whole files in this plan.
- The guard proves worktree ownership, not a direct task's per-file authority. The caller retains responsibility for task write-scope compliance; explicit operands and fixed tool target/rule lists bound the tool's writes.

## Tasks

- [ ] Review the five diagnosed files and confirm each reference's intended binding. Resolve the guarded EMPTY_CHAIN_DIGEST initializer without changing its value; add the missing annotation imports where appropriate.
- [ ] Add the pinned dependency files, Ruff rule configuration and mirrored lint entrypoints with precise target selection, version checking, read-only defaults and guarded F541-only fixes.
- [ ] Wire root lint, generated CI and both change-aware selectors to the check command; extend the command allowlist only for its non-mutating form.
- [ ] Register PythonLintTest once through tests/test-validation-tools.py. Use real Ruff on isolated root and generated fixtures; prove every selected rule with a defect and a valid counterpart, and prove repairs remove the diagnosis.
- [ ] Test missing and mismatched tool versions, invalid configuration, nonempty target selection, path escapes, failed preflight with no partial writes, fix idempotence and preservation of project-owned files.
- [ ] Run the real check against the complete current initial scope in the focused suite. Do not substitute fake tool output or skip tests when Ruff is missing. Reuse existing lifecycle tests for the touched binding behavior.
- [ ] Register all new files and mirrored parity in copier_inventory.py and check-copier-template.py. Update root and generated validation guidance and generated-CI assertions.
- [ ] Review and validate the final in-scope diff; commit the lint implementation independently of later formatter changes, then use the ordinary completion and publication lifecycle.
- [ ] Extend the update-source fixture inventory and real Copier-update scenarios for the new managed files; assert project-owned byte preservation and existing validation retention. Read the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite.

## Validation Notes

- The owner requested implementation of the active and backlog plans on 2026-09-16. Plan 376 is checked and published, leaving the serial implementation slot free. This plan starts the declared lint, type-checking and formatting sequence; the latter two remain unstarted until their predecessors are checked.
- Use the existing parent-direct workflow because the declared scope changes validation authority, dependency pins and guarded writes. Parallel candidate generation cannot admit this scope. Preserve all accepted requirements and run a fresh observed review-route probe before product edits.
