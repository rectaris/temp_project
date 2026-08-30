# Bind fixture editing acceptance to the inventory

status: backlog
primary_invariant: the focused checker accepts a Git staging outside the inventory region only when the inventory itself declares the staged path, so no editing command can buy acceptance for a path no inventory line carries
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 247 must not resume until this plan is checked
checked_summary_ja: inventoryが宣言しないpathをeditingで通す抜け道を塞ぎ、staging受理をinventory記載pathに束縛する。

## Decisions

- Repair the acceptance side rather than widen the rejection side. Checked Plan 245 already reports a staging that nothing writes; the defect is that any reachable editing command naming a path under the update-source roots buys acceptance without the inventory being consulted.
- Compare against the inventory file the fixture reads, because the acceptance clause binds copy and staging inputs to one inventory rather than to the set of paths some command happens to touch.
- Own the validator and its test together, because narrowing an acceptance carve-out is only safe with the mutation coverage that proves the committed fixture still passes.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [ ] Reproduce the admission read-only by splicing `sed -i "1r $root/AGENTS.md" "$update_source/NOTICE"` and `fixture_git "$update_source" add -- NOTICE` after the inventory loop and confirming the committed gate accepts it.
- [ ] Bind the editing carve-out to the paths the inventory declares, and keep the committed fixture and its three legitimate edit-then-stage sites accepted unchanged.
- [ ] Add mutation coverage for an editing command that reads an out-of-inventory source, for an in-place edit of an undeclared path, and for the unchanged legitimate sites.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded as High finding 1 of the Plan 247 independent review and was confirmed in the main session against the committed gate with `tests/copier-update.sh` left byte-identical.
