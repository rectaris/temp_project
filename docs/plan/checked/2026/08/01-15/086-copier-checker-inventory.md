# Extract Copier checker inventory data

status: checked
primary_invariant: preserve every checker CLI output and validation result while moving static repository inventory out of the entrypoint
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
  - scripts/copier_template_inventory.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - python3 -m py_compile scripts/check-copier-template.py scripts/copier_template_inventory.py
validation:
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Move static source paths, generated paths, Copier question schemas, and conditional generation rules from the checker entrypoint into one focused importable module while preserving every existing CLI output entry and adding only the new module where inventory completeness requires it.
  - Keep `scripts/check-copier-template.py` as the only public CLI entrypoint and preserve all existing argument and error behavior.
  - Include the new module in the required source inventory and derive Python compilation coverage from that inventory.
  - Keep generated-required, source-shell, and docs-fixture outputs byte-identical; keep every existing source-required and source-python entry in order and add only `scripts/copier_template_inventory.py`.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: Copier検査の静的inventoryを専用モジュールへ分離し、既存CLI出力を保持した。

## Decisions

- Keep validation functions and CLI dispatch in `scripts/check-copier-template.py`.
- Keep the extracted module data-only and free of repository reads or process effects during import.
- Implement in the parent session because the source inventory defines validation authority.

## Tasks

- [x] Extract static inventory and schema constants.
- [x] Preserve CLI output baselines and focused validation.
- [x] Complete independent review and authoritative validation.
- [x] Archive and commit the accepted change.

## Validation Notes

- `scripts/check-copier-template.py` decreased from 1,633 to 1,247 lines; the 423-line static inventory is isolated in `scripts/copier_template_inventory.py`.
- Generated-required, source-shell, and docs-fixture outputs matched the pre-change baselines byte-for-byte. Source-required and source-python preserved every existing entry in order and added only the new inventory module.
- `python3 scripts/check-copier-template.py` and Python compilation passed.
- Independent review compared all 36 checker function ASTs and every extracted constant with the pre-change revision, found no import cycle or import-time repository effects, and reported zero High or Medium findings.
- Workflow lint and smoke passed with `TMPDIR=/dev/shm`; Actionlint remained unavailable and was skipped by unchanged behavior.
- The first Copier update invocation used `/dev/shm` and failed because the temporary update repository crossed a filesystem discovery boundary. Re-running only `tests/copier-update.sh --require-copier` in its default same-filesystem temporary root passed.
- `python3 scripts/validate-changes.py --all` selected both checker modules for compilation, and `git diff --check` passed.
