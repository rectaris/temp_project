# Format the initial Python validation tools with a guarded writer and a read-only check

status: backlog
primary_invariant: The declared validation scripts use one pinned format, while formatting preserves their parsed behavior and writes only explicitly authorized files.
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
  - {"evidence":"At d61b41e Ruff 0.15.7 `format --check --isolated --target-version py311` reports scripts/render-plan-overview.py and both validate-changes.py copies as needing formatting and the other three targets as formatted; no source was rewritten.","kind":"bounded_prototype"}
  - {"evidence":"Formatting scripts/validate-changes.py as-is rewrites its active plan index grammar block, which check-copier-template.py requires to be byte-identical across twelve sources, ten of them outside this plan's targets, so the unprotected formatter output fails the template check.","kind":"reproduced_defect"}
  - {"evidence":"With `# fmt: off` before the grammar start marker and `# fmt: on` after the end marker, Ruff 0.15.7 left the block byte-identical, kept ast.dump equal, and a second --check pass reported the output formatted.","kind":"bounded_prototype"}
  - {"evidence":"Checked plan 353 ships the pip/uv Ruff 0.15.7 pin, paired tools/python-quality directories, python3 -I launch with a sysconfig Ruff lookup, the worktree guard for writes and PYTHON_ISOLATED_SCRIPT_ARGUMENTS; lint-python.py is also listed in SESSION_SERIAL_COMMANDS. This plan reuses all of them.","kind":"existing_mechanism"}
completion_conditions:
  - `python3 -I scripts/format-python.py --check` checks exactly the six root targets and the generated command the three managed targets with Ruff 0.15.7 and only the paired ruff-format.toml, fails on unformatted, missing or extra targets, a wrong Ruff version or malformed settings, and writes nothing.
  - --write requires the live task-worktree guard and explicit file operands, checks every operand against the fixed target inventory and rejects symlink escapes before the first write, and one invalid operand prevents every write.
  - After formatting, all six targets pass --check and a second --write pass changes no byte; a committed pre-format fixture formatted by the real Ruff keeps ast.dump, comment tokens and string values unchanged.
  - Root required lint and generated CI run the check through python3 -I, both allowlists admit only that --check form, format-python.py is session-serial like lint-python.py, and the change-aware selector behavior is unchanged.
  - Paired entrypoints, ruff-format.toml and format-targets.json are registered and byte-equal under the documented mapping, the lint-only ruff.toml is unchanged, and the grammar block and both check-codex-toml.py copies stay aligned.
  - A real Copier update installs the managed formatter, its settings and the formatted managed targets while preserving product code, product formatter and dependency settings, project-owned policy and previously required validation.
completion_witness_map:
  - {"condition_sha256":"sha256:6421cfcb8bb512d768ddd79e927014a61cc87eecb35b3b5344e461fa1b0a3665","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:39649b5da35a99384b10cff851a00e070b3e7425cf69a6522178ecc4140cd4ce","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:bbc67ecffbf84cf9f1ad3b729316a3ac30b60006ccf9208cd4c7fc89b3e40699","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:7626d90fc43f0c92c5b00720c3990e1c0e6b558d679a377f36883e1e0250cd59","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:4ac52444a7c9da13ecb31f6dcac5f0bf96904c60f840c37c785e2eafba368cd1","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:aedab337f81e8e8519c8e9668e0b7fc4f24c4ba2bd9de48d906fa2e547579049","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - tools/python-quality/ruff-format.toml
  - template/.project-agent-workflow/tools/python-quality/ruff-format.toml
  - tools/python-quality/format-targets.json
  - template/.project-agent-workflow/tools/python-quality/format-targets.json
  - scripts/format-python.py
  - template/.project-agent-workflow/scripts/format-python.py
  - scripts/check-codex-toml.py
  - template/.project-agent-workflow/scripts/check-codex-toml.py
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/lint-project-workflow.sh
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
  - tests/validation_tools/python_format.py
  - tests/validation_tools/generated.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/worktrees.py
  - tests/fixtures/python-format/unformatted-source.txt
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
  - tools/python-quality/ruff.toml
  - docs/plan/checked/2026/09/16-31/353-enforce-bounded-python-lint.md
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
  - A contributor can apply the agreed Python format mechanically and detect drift locally or in CI, with an idempotent change confined to the selected files and no behavior or project-owned content changes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c4cef9d8d978fe1dc05c122cf8f3f1ac7c25980e5997184c8279c5f6681ac151","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - docs/plan/checked/2026/09/16-31/353-enforce-bounded-python-lint.md
checked_summary_ja: 検証用Pythonスクリプト6件の書式をRuffで統一し、整形漏れをローカルとCIで検査する。

## Decisions

- Run this plan before plan 365. It needs only plan 353's Ruff installation, and the two plans share their validation wiring files, so they execute serially.
- Implement parent-direct with the existing execution ledger, adversarial preflight and independent-review gates. Keep the authoritative commands scripts/lint-project-workflow.sh and tests/smoke.sh; their content gains the format check, their invocation does not change.
- Store format settings in a separate paired tools/python-quality/ruff-format.toml: required-version ==0.15.7, line length 88, four-space indentation, double quotes, LF line endings, target Python 3.11, preview off and docstring-code formatting off. Leave the lint-only ruff.toml and scripts/lint-python.py unchanged, because lint-python.py requires that file to equal its fixed settings.
- Invoke Ruff only with --config pointing at ruff-format.toml, resolve it through sysconfig as lint-python.py does, launch every caller with python3 -I, and keep format-python.py standard-library only.
- Store the explicit paired target lists in format-targets.json. The generated targets are the three managed .project-agent-workflow/scripts files.
- --check is the read-only default. --write requires the existing task-worktree guard plus explicit file operands that are all preflighted against the target inventory before the first write; no implicit full-set write exists.
- Protect the shared active plan index grammar block in both validate-changes.py copies with `# fmt: off` before its start marker and `# fmt: on` after its end marker. This is the only permitted non-formatter edit in the targets; the block bytes stay identical to the other ten sources.
- Apply only formatter output to the targets otherwise. Keep imports, logic and existing suppressions, and keep Jinja sources, plan records, recorded evidence and downstream product files outside formatting.
- Record the one-time equivalence of the six real targets in Validation Notes from a throwaway comparison of pre-format and formatted ast.dump, comment tokens and string values; the durable test uses the committed pre-format fixture.

## Tasks

- [ ] Resolve plan 353's checked archive, rerun the Ruff check and the fmt: off prototype on the six targets at the current HEAD, and capture their pre-format bytes outside the repository.
- [ ] Add the paired ruff-format.toml and format-targets.json files and the paired format-python.py entrypoints.
- [ ] Wire the check into root required lint, the generated workflow and both allowlists as a python3 -I --check form, and register format-python.py in both session-serial command lists.
- [ ] Add the fmt: off/on markers around both grammar blocks, apply the formatter to the six targets, verify equivalence and a zero-diff second pass, and record the result in Validation Notes.
- [ ] Add PythonFormatTest: real Ruff on the committed pre-format fixture, the real targets and rendered managed targets; missing and extra targets, paths outside the inventory, symlink escapes, mixed valid and invalid write requests with no partial writes, wrong versions and malformed settings.
- [ ] Register every new file and mirror relation in the inventory and template checker, extend the generated-layout and plan-command tests, and update root and generated validation guidance.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite.
- [ ] Review the tooling change and the formatted source as distinct parts, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle.

## Validation Notes

- Pre-activation review at d61b41e: the original plan depended on plan 365 without needing its output, put format settings into the lint-only ruff.toml that lint-python.py rejects, and would have broken the grammar-block alignment. Those three points are resolved above.
