# Check types in the initial Python validation tools and their generated counterparts

status: backlog
primary_invariant: Pinned type checking covers each declared validation script and its generated counterpart without silently omitting hidden template files or changing downstream product configuration.
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"npm pyright@1.1.407 on Node 24.14.1 at d61b41e: one configuration listing all six targets with exclude [] analyzed only the three root files; files below template/.project-agent-workflow were skipped even when named explicitly, so one root-level configuration cannot cover the template layout.","kind":"bounded_prototype"}
  - {"evidence":"A pyrightconfig.json placed in tools/python-quality and one in template/.project-agent-workflow/tools/python-quality, each with basic mode, Python 3.11 and ../../scripts/<target> includes, analyzed exactly three files each with zero diagnostics; a seeded int-returned-as-str error was reported.","kind":"bounded_prototype"}
  - {"evidence":"Checked plan 353 ships paired tools/python-quality directories, python3 -I launch, PYTHON_ISOLATED_SCRIPT_ARGUMENTS, change-selector wiring and PythonLintTest. Neither CI workflow sets up Node today, and root and template .gitignore already ignore node_modules/.","kind":"existing_mechanism"}
completion_conditions:
  - `python3 -I scripts/typecheck-python.py` runs pinned Pyright 1.1.407 on Node 24 in basic mode for Python 3.11 over the three root and three template targets through two per-layout configurations, and the generated command checks the three managed targets.
  - Each run asserts that its configuration analyzed exactly its declared targets and fails on a missing target, a hidden-path omission, a wrong Pyright or Node version, a lockfile mismatch, malformed configuration, unresolved imports or any type error, without downloading, installing or rewriting source.
  - Seeded argument, return and optional-access errors fail while the corrected cases pass, and the only suppressions in the targets are the existing type: ignore comments.
  - Root lint, root CI, generated CI and both change selectors run the check through python3 -I after an explicit `npm ci` of the managed tool directory, and both allowlists admit only that form.
  - Paired package manifests, lockfiles, configurations and entrypoints are registered and byte-equal under the documented mapping, and copier.yml excludes node_modules from generation.
  - A real Copier update installs the managed type-check additions while preserving existing product code, product dependency manifests, project-owned policy/configuration and previously required validation.
completion_witness_map:
  - {"condition_sha256":"sha256:651b3ef27f2fb6d6aec4517eda0b70851b379d84c75b894d112355554ff7d7ea","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:e2e445d9121ff47ee014549afe9822b141ccef7f9ea86a38249374d7e9a9843c","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d7846201dd01585257e0afa453174ab9a2af04dc85c494dfedb46a5edb2a2584","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:dd4784722c29bfd174b12096d606d10ce03a60971d9ba562fad0e8975662facd","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f20a6cc3abfc86cecdaa7846c8683350025a15eaa411199f34e7a43bd37f5c50","witness":"python3 scripts/check-copier-template.py"}
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
  - scripts/check-codex-toml.py
  - template/.project-agent-workflow/scripts/check-codex-toml.py
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - .github/workflows/ci.yml
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/lint-project-workflow.sh
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - copier.yml
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
  - scripts/lint-python.py
  - docs/plan/checked/2026/09/16-31/353-enforce-bounded-python-lint.md
  - docs/plan/backlog/366-format-initial-python-validation-tools.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
  - references/orchestration.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
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
  - docs/plan/backlog/366-format-initial-python-validation-tools.md
checked_summary_ja: npm版Pyright 1.1.407とNode 24で、検証用Pythonスクリプトの引数と戻り値の型を検査する。

## Decisions

- Start only after plan 366 is checked, resolving its archive through docs/plan/checked.md before activation; both plans edit the same validation wiring, and the formatted targets then stay under the format check.
- Implement parent-direct with the existing execution ledger, adversarial preflight and independent-review gates, and keep the full required validation suite.
- Pin the official npm package pyright to exactly 1.1.407 in byte-identical paired tools/python-quality/package.json and package-lock.json. Install it only by an explicit `npm ci --prefix tools/python-quality` setup step; never use npx, a global install or an automatic download inside a check.
- Add Node 24 setup and that npm ci step to root CI before scripts/lint-project-workflow.sh and to the generated workflow before its checks. Document the same local setup. Never create or change a generated project's product package.json, lockfile or pyproject.toml.
- Place one pyrightconfig.json in each managed tool directory with basic mode, Python 3.11, explicit ../../scripts/<target> file includes, exclude [] and missing-import reporting on. The root command runs both the root and the template configuration with the root installation; the generated command runs its own. Pyright skips paths with a dot-directory component below its project root, so a single root configuration is not admissible.
- Keep typecheck-python.py standard-library only and launch it with python3 -I. Resolve Pyright only as <tool dir>/node_modules/.bin/pyright, verify its installed version and the lockfile digest, require Node major 24, run --outputjson, and require filesAnalyzed to equal the number of explicit includes, each of which must exist.
- Keep the dependency model of plan 353: the pinned tool is provided by the validating host and the check fails closed where it is absent. Rendered-fixture tests copy the root installation into the fixture's managed tool directory after asserting byte-equal lockfiles; nothing is installed inside template/. Extending the sandboxed runner's dependency snapshot is outside this plan.
- Type checking only reports defects. Fix any real defect within the three-script scope while preserving runtime behavior; do not add Any, casts or new ignores to silence a finding, and keep the existing type: ignore comments.
- Wire root lint, root and generated CI, and both change selectors to the complete check; a change to a target or its tool configuration selects it.

## Tasks

- [ ] Resolve plans 353 and 366 to their checked archives and rerun the two-configuration prototype against the published baseline before implementation.
- [ ] Add the paired package manifests, lockfiles and per-layout configurations, and add node_modules to copier.yml exclusions.
- [ ] Implement the paired typecheck-python.py commands with pinned lookup, version and lock verification, exact coverage assertion and clear failures.
- [ ] Extend root CI, generated CI, root lint, both change selectors, and both allowlists without replacing existing validation.
- [ ] Add PythonTypesTest with real Pyright on every target and on rendered fixtures; seeded argument, return and optional-value errors and corrected cases; absent files, hidden-path omission, invalid configuration, missing imports, wrong Pyright or Node versions, lock mismatch; no source or configuration writes.
- [ ] Register paired files and mappings in the inventory and template checker, and document the coverage and the local setup in root and generated validation guidance, stating that render-plan-overview.py wrappers carry little checkable code.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite.
- [ ] Review, run the focused checks, then the full validation suite once, commit separately from plan 366's formatting, and publish through the ordinary lifecycle.

## Validation Notes

- Pre-activation review at d61b41e: plan 353 installed Ruff through pip and uv with no Node or npm, so this plan introduces the Node toolchain itself. The owner chose npm Pyright with Node 24 over a pip-installed alternative on 2026-09-26. The earlier six-file prototype at b1c909a did not reproduce: a single configuration skips the hidden template directory.
