# Modularize large AI-facing test sources

status: checked
primary_invariant: preserve all existing test behavior and command paths while reducing the source range needed for one test-domain change
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
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
  - tests/validation_tools_support.py
  - tests/validation_tools_plan.py
  - tests/validation_tools_external.py
  - tests/validation_tools_changes.py
  - tests/validation_tools_generated.py
  - tests/test-hooks.py
  - tests/hook_test_support.py
  - tests/hook_tests_gates.py
  - tests/hook_tests_logging.py
  - tests/hook_tests_context.py
  - tests/hook_tests_semantic.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/lint-project-workflow.sh
  - scripts/plan_validation_commands.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-hooks.py
validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-hooks.py
  - python3 scripts/plan_validation_commands.py --self-test
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Split validation-tool and Hook test domains into focused modules while retaining the existing aggregate command paths.
  - Keep every existing unittest case discoverable exactly once through each aggregate command and preserve its exit status.
  - Keep shared fixture and repository-path setup in small support modules instead of duplicating it across domain modules.
  - Add every new source module to the deterministic repository inventory and Python compilation checks.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 大規模な検証テストとHookテストを機能別モジュールへ分割し、既存コマンドを維持した。

## Decisions

- Keep `tests/test-validation-tools.py` and `tests/test-hooks.py` as compatibility entrypoints.
- Use non-discovery module names for extracted suites so generic discovery does not execute imported classes twice.
- Implement in the parent session because the changed files define validation authority.

## Tasks

- [x] Extract shared helpers and validation-tool test domains.
- [x] Extract shared helpers and Hook test domains.
- [x] Preserve source inventory, aggregate counts, and direct module execution.
- [x] Run focused validation, independent review, and the authoritative suite.
- [x] Archive and commit the accepted change.

## Validation Notes

- `python3 tests/test-validation-tools.py`: 31 tests passed through the compatibility entrypoint.
- `python3 tests/test-hooks.py`: 34 tests passed through the compatibility entrypoint.
- All eight focused test modules passed when executed directly, and the aggregate entrypoints remained executable.
- Test-method inventory comparison found no missing or added cases relative to the pre-split files.
- Independent review found one Medium executable-mode regression; the mode and hidden wildcard-import dependencies were corrected. Final rereview reported zero unresolved High or Medium findings.
- Authoritative `python3 scripts/plan_validation_commands.py --self-test`, Copier template check, workflow lint, smoke, changed-file validation, and `git diff --check` passed with `TMPDIR=/dev/shm` to avoid the ambient `/tmp/.git` boundary.
- Actionlint was unavailable and skipped by the unchanged smoke behavior; no GitHub Actions workflow changed.
