# Format the initial Python validation tools with a guarded writer and a read-only check

status: backlog
primary_invariant: The declared validation scripts use one pinned format, while formatting preserves their parsed behavior and writes only explicitly authorized files.
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
  - {"evidence":"Ruff 0.15.7 format --check --isolated on the six selected root/template validation scripts reported three needing formatting and three already formatted at source b1c909a; no source bytes were changed.","kind":"bounded_prototype"}
  - {"evidence":"Plan 364 supplies the pinned Ruff installation and paired configuration; plan 365 supplies the bounded six-file coverage. Existing worktree guards and command allowlists distinguish check commands from authorized writes.","kind":"existing_mechanism"}
  - {"evidence":"Formatting each selected file through Ruff stdin preserved ast.dump(ast.parse(source)) and all tokenize.COMMENT token strings in six comparisons. Only three formatted outputs differed; no source files were rewritten.","kind":"bounded_prototype"}
completion_conditions:
  - Required local and generated CI formatting checks use Ruff 0.15.7 with pinned settings and reject unformatted or missing files in the documented six-file root scope or three-file generated scope without rewriting source.
  - Explicit formatting requires a live task worktree and explicit file operands; every operand is checked against the fixed target inventory before any write, and an invalid operand prevents every write.
  - Formatting the selected scripts preserves their AST, string values, comments and required mirror relationships, and a second pass produces no diff; Jinja templates, history and downstream product files are untouched.
  - Root and generated formatting entrypoints, target inventories and settings are registered and mechanically checked for matching behavior under their documented path mapping.
  - A real Copier update installs the managed formatter and formatting baseline while preserving product code, product formatter/dependency settings, project-owned policy and previously required validation.
completion_witness_map:
  - {"condition_sha256":"sha256:59c2b797cd56dc024770e35c319476451b8daa6d2d2352a8746386f4fd7c1934","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:44d8fca7935f9ff42cd4d5704efd982417417ec3a2f084f4f826a0035bfd8dff","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:7108cbbd4621db3da2dac0f612deb12c3883b95c385d32e7baa3807f611eae98","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a92d8c28cd1acbb04b4d6817de52a367caf03934d724e686524d638936a974f6","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:1469f4a785907c3d22359fd6dda6b8e25265531afefa2e017cc8ab6a627145ca","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - tools/python-quality/ruff.toml
  - template/.project-agent-workflow/tools/python-quality/ruff.toml
  - tools/python-quality/format-targets.json
  - template/.project-agent-workflow/tools/python-quality/format-targets.json
  - scripts/format-python.py
  - template/.project-agent-workflow/scripts/format-python.py
  - scripts/lint-project-workflow.sh
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
  - tests/validation_tools/python_format.py
  - tests/validation_tools/generated.py
  - tests/validation_tools/plan.py
  - references/validation.md
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - scripts/check-codex-toml.py
  - template/.project-agent-workflow/scripts/check-codex-toml.py
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/backlog/365-check-types-in-python-validation-tools.md
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
  - A contributor can apply the agreed Python format mechanically and detect drift locally or in CI, with an idempotent change confined to the selected files and no behavior or project-owned content changes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c4cef9d8d978fe1dc05c122cf8f3f1ac7c25980e5997184c8279c5f6681ac151","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - docs/plan/backlog/365-check-types-in-python-validation-tools.md
checked_summary_ja: 検証用Pythonスクリプトの書式を統一し、整形漏れを検査する。

## Decisions

- Start after plan 365 has completed, resolving its checked archive before activation. Execute serially after lint and type checking; keep this work unstarted in backlog until implementation is requested.
- Use parent-owned implementation for the guarded formatter and validation integration with the existing independent-review and ledger gates. Keep the authoritative lint and smoke commands unchanged.
- Reuse Ruff 0.15.7. Pin line length 88, four-space indentation, double quotes, LF line endings, target Python 3.11, preview disabled and docstring-code formatting disabled in the paired Ruff configuration.
- Format only check-codex-toml.py, render-plan-overview.py and validate-changes.py under root scripts and their template counterparts. Generated targets are the corresponding three managed scripts; store explicit paired target lists.
- Add paired scripts/format-python.py commands. --check is read-only and the default; --write requires the existing task-worktree guard plus explicit file operands and fixed-inventory checks for all requested paths before the first write.
- Check mode covers the complete target set. Write mode accepts only explicit file operands. The caller owns task-scope compliance; worktree ownership is not per-file authority, and no implicit full-set write is permitted.
- Wire the full format check through required root lint and generated CI. Admit only --check in plan validation. Keep the change-aware selector's behavior unchanged in this plan.
- Do not change imports, logic or lint suppressions in the six formatting targets. Apply only formatter output there, in a commit separate from the lint repairs and type-checking implementation.
- Keep Jinja sources, archived plans, recorded evidence and downstream product files outside automatic formatting. Existing project-owned formatters and their configuration remain unchanged.

## Tasks

- [ ] Resolve the checked predecessor and capture exact pre-format bytes, ASTs, comments and string values of the six targets from that published baseline.
- [ ] Add paired explicit target lists and guarded formatting entrypoints, reusing the pinned Ruff installation and format settings.
- [ ] Add the non-mutating check to root required lint, generated workflow and command allowlists, with clear missing-tool/version/configuration failures and no implicit dependency installation.
- [ ] Apply Ruff only to the six declared targets. Verify AST and literal equivalence, retained comments, mirror compatibility and a zero-diff second pass; do not hand-edit functional code while formatting.
- [ ] Register PythonFormatTest once in tests/test-validation-tools.py. Use real Ruff for malformed-format and already-formatted examples, the real target set and rendered managed targets.
- [ ] Test missing targets, paths outside the target inventory, symlink escapes, mixed valid/invalid write requests, no partial writes on preflight refusal and preservation of unrelated product files and configuration.
- [ ] Register every new file and mirror relation in the inventory and alignment checker. Update root/generated validation guidance and generated workflow assertions.
- [ ] Review the tooling changes and the mechanically formatted source as distinct parts of this commit, run focused and required validation, then complete and publish through the ordinary lifecycle.
- [ ] Extend the update-source fixture inventory and real update scenarios for the formatter and changed managed targets. Read the whole v1.4.5 migration guardian rule before running the update suite and assert preserved project-owned bytes and existing validation.

## Validation Notes
