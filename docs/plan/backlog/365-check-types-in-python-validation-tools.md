# Check types in the initial Python validation tools and their generated counterparts

status: backlog
primary_invariant: Pinned type checking covers each declared validation script and its generated counterpart without silently omitting hidden template files or changing downstream product configuration.
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
  - {"evidence":"Pyright 1.1.407 basic mode with Python 3.11, explicit includes, exclude: [] and separate script-directory execution environments analyzed all six selected root/template files with zero errors and warnings at source b1c909a.","kind":"bounded_prototype"}
  - {"evidence":"A default CLI probe analyzed only three files despite six explicit paths. An explicit configuration analyzed six; adding the two script-directory import roots resolved two missing-import diagnostics without suppressions.","kind":"bounded_prototype"}
  - {"evidence":"The root and generated validate-changes.py selectors already call the command allowlist. Plan 364 introduces pinned managed-tool setup and test registration, which this plan extends after 361 is checked.","kind":"existing_mechanism"}
completion_conditions:
  - Required local and CI type checks use Pyright 1.1.407 basic mode and Python 3.11 for the three selected root scripts and their three template counterparts; generated projects check the corresponding three managed scripts.
  - Coverage explicitly includes hidden template paths and verifies the complete expected file set; invalid arguments, return types and optional-value access fail while corrected cases pass.
  - Missing tools, wrong versions, missing expected files, malformed configuration and unresolved imports fail clearly without downloads, source rewrites or suppression-based success.
  - The paired entrypoints and profile-specific type configurations are registered and mechanically checked for matching rules and the documented root-to-generated path mapping.
  - A real Copier update installs the managed type-check additions while preserving existing product code, product dependency manifests, project-owned policy/configuration and previously required validation.
completion_witness_map:
  - {"condition_sha256":"sha256:1bcf9e3a793c0cf521313f62a0fd6d78186840f4998c599d258a802b44c5fa5c","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:72da3e75ab3fbb9fc32122fb40a16718b3e462f2086235404ffc1c9b03ba91f8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:e26c702638acfdc50700d0f4f9705356d69b88534104a182d4db62379015c07b","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:6f533462133d81c80933756306534b52d1ca43a89d6ce753abbcef3fe89647c3","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:8cb0a900f81ebe2e832addf446a5db916ab44748edfc888e7279b9b7d8fe19f2","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - tools/python-quality/package.json
  - tools/python-quality/package-lock.json
  - template/.project-agent-workflow/tools/python-quality/package.json
  - template/.project-agent-workflow/tools/python-quality/package-lock.json
  - tools/python-quality/pyrightconfig.json
  - template/.project-agent-workflow/tools/python-quality/pyrightconfig.json
  - scripts/typecheck-python.py
  - template/.project-agent-workflow/scripts/typecheck-python.py
  - .github/workflows/ci.yml
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/lint-project-workflow.sh
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/check-codex-toml.py
  - template/.project-agent-workflow/scripts/check-codex-toml.py
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
  - tests/validation_tools/python_types.py
  - tests/validation_tools/changes.py
  - tests/validation_tools/generated.py
  - tests/validation_tools/plan.py
  - references/validation.md
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/replanned/2026/09/16-31/364-enforce-bounded-python-lint.md
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
  - The initial validation tools receive reproducible type checks that detect seeded type mistakes in both layouts and cannot pass by omitting files, while all existing validation and downstream product settings are preserved.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:145a7519dbd68b50cefe1ee0210df4e57c1e083752b5a61fdf1089e826e28045","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Start only after the bounded Python lint plan reconstructed from plan 364 is checked, because this plan extends the pinned managed-tool setup and test registration that plan installs.
checked_summary_ja: 検証用Pythonスクリプトの引数や戻り値の型を検査する。

## Decisions

- Start only after docs/plan/checked/2026/09/16-31/353-enforce-bounded-python-lint.md, the owner-authorized reconstruction of the stopped plan 364, which is checked. Keep this plan in backlog until implementation is requested; execute serially.
- Use parent-owned implementation for validation and dependency changes, with the existing independent-review and ledger requirements. Preserve the full required validation suite.
- Pin the official npm package pyright to 1.1.407 in paired tools/python-quality/package.json and package-lock.json files. Use npm ci during explicit setup; never use npx with automatic downloads inside a validation command.
- Use Node 24 in root and generated CI and document it for local setup. Install only the managed tool directory; do not create or change a generated project's product package.json, lockfile or pyproject.toml.
- Check scripts/check-codex-toml.py, scripts/render-plan-overview.py and scripts/validate-changes.py plus their template counterparts. Generated scope is the corresponding three .project-agent-workflow/scripts files.
- Use basic mode, Python 3.11, explicit include lists, exclude: [] and separate execution environments for the two script directories. Keep missing-import and type diagnostics enabled; do not use Any or ignores to silence new failures.
- Add paired scripts/typecheck-python.py commands and tools/python-quality/pyrightconfig.json files. Assert expected coverage from supported Pyright file enumeration and analysis output, not a zero-error count alone.
- Type checking only reports defects. Resolve any real post-361 defect within the declared three-script scope and preserve runtime behavior; no automatic type-driven source rewrite is authorized.
- Wire root lint, generated CI and paired change-aware selectors to the check. Changes to a target or its tool configuration must select the complete bounded check.

## Tasks

- [ ] Resolve plan 364 to its checked archive before activation and verify its published lint baseline. Recheck the bounded six-file type prototype against that baseline before implementation.
- [ ] Add paired locked Pyright npm dependencies and explicit root/generated type configurations, preserving separate import resolution for each script directory.
- [ ] Implement the paired read-only type-check commands with deterministic target enumeration, pinned executable lookup and clear failures for missing coverage or unavailable dependencies.
- [ ] Extend root and generated CI setup, required root lint, both change selectors and the validation-command allowlists without replacing existing validation.
- [ ] Register PythonTypesTest once in tests/test-validation-tools.py. Run real pinned Pyright on every selected root/template file and on rendered fixtures; verify argument, return and optional-value errors and corrected cases.
- [ ] Test absent files, hidden managed paths, unrelated product type errors, invalid config, missing imports and wrong tool versions. Prove no source/configuration writes and preserve product dependency manifests.
- [ ] Register paired files and config path mappings in the inventory and alignment checker. Document the bounded coverage honestly and the exact explicit local setup.
- [ ] Review, validate and commit this type-checking change separately from lint repairs and subsequent formatting, then complete and publish through the ordinary lifecycle.
- [ ] Extend the update-source fixture inventory and real update scenarios for the managed type tooling. Read the full v1.4.5 migration guardian rule before the update suite; assert that project-owned bytes and existing validation are retained.

## Validation Notes
