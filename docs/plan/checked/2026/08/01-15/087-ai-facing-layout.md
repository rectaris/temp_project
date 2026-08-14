# Organize AI-facing script and test sources

status: checked
primary_invariant: preserve existing command paths and test behavior while reducing the root-level source set an agent must inspect for one focused change
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - docs/plan/
  - scripts/AGENTS.md
  - scripts/check-copier-template.py
  - scripts/copier_template_inventory.py
  - scripts/project_workflow/
  - tests/AGENTS.md
  - tests/test-hooks.py
  - tests/test-validation-tools.py
  - tests/hook_test_support.py
  - tests/hook_tests_context.py
  - tests/hook_tests_gates.py
  - tests/hook_tests_logging.py
  - tests/hook_tests_semantic.py
  - tests/hooks/
  - tests/validation_tools_support.py
  - tests/validation_tools_changes.py
  - tests/validation_tools_external.py
  - tests/validation_tools_generated.py
  - tests/validation_tools_plan.py
  - tests/validation_tools/
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - python3 tests/test-hooks.py
  - python3 tests/test-validation-tools.py
validation:
  - python3 scripts/check-copier-template.py
  - python3 tests/test-hooks.py
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Keep every existing documented and aggregate command path unchanged while relocating only imported implementation and focused test modules.
  - Move the Copier inventory, Hook test support and domains, and validation-tool test support and domains into responsibility-specific importable packages.
  - Keep every existing Hook and validation-tool unittest case discoverable exactly once through its aggregate command and preserve aggregate exit behavior.
  - Add concise scripts/AGENTS.md and tests/AGENTS.md files that route agents by responsibility, distinguish directly executed files from imported implementation, and name focused validation without duplicating root policy.
  - Update deterministic source inventory and Python compilation coverage for every added, moved, or removed source path.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: スクリプトとテストの公開コマンドを維持し、内部モジュールを責務別ディレクトリへ整理して局所的なエージェント案内を追加した。

## Decisions

- Compatibility entrypoints are the existing files whose command paths remain unchanged while they dispatch to relocated implementation.
- Responsibility packages are importable directories that contain implementation files sharing one change reason.
- Keep compatibility entrypoints at the scripts/ and tests/ roots.
- Create scripts/project_workflow/, tests/hooks/, and tests/validation_tools/ as responsibility packages without moving unrelated standalone commands.
- Keep local AGENTS.md guidance short and defer shared policy to the root AGENTS.md.
- New concise files at scripts/AGENTS.md and tests/AGENTS.md describe local placement, routing, invariants, and validation without duplicating root policy.
- Existing repository inventory and validation checks classify the relocated files and verify the retained entrypoint imports.
- Use bounded parent implementation because the relocation changes validation-authority paths; require independent review before authoritative validation.

## Tasks

- [x] Add local agent-routing guidance for scripts/ and tests/.
- [x] Relocate the Copier inventory module and update its compatibility entrypoint and source inventory.
- [x] Relocate the Hook and validation-tool test modules and update their aggregate compatibility entrypoints.
- [x] Prove test inventory parity and run focused validation.
- [x] Complete independent review and authoritative validation.
- [x] Archive and commit the accepted change.

## Validation Notes

- `scripts/AGENTS.md` and `tests/AGENTS.md` now route agents from stable root commands to responsibility-specific implementation and test packages.
- `scripts/check-copier-template.py`, `tests/test-hooks.py`, and `tests/test-validation-tools.py` kept their existing paths and passed from both the repository root and an unrelated working directory.
- AST comparison against the pre-change sources found identical Hook and validation-tool test method sets: 34 and 31 respectively, with no missing or added methods.
- Aggregate unittest loading passed 34 and 31 tests exactly once; internal domain module names remain outside generic `test*.py` discovery.
- The deterministic inventory contains every new package and guide file, excludes the moved legacy paths, and compiled all 69 inventoried Python sources.
- Independent review reported zero unresolved High or Medium findings. Pytest collection was unavailable because pytest is not installed; unittest loading and filename checks covered the duplicate-discovery invariant.
- Authoritative `python3 scripts/check-copier-template.py`, both aggregate tests, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `tests/copier-update.sh --require-copier`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed.
- Actionlint was unavailable and skipped by the unchanged validation behavior; no GitHub Actions workflow changed.
