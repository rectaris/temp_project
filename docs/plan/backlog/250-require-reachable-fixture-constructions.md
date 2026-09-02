# Require reachable pre-schema fixture constructions

status: backlog
primary_invariant: the focused checker rejects a bound pre-schema construction whose enclosing command list can be skipped, so the constructed plan, archive, and contract cannot be made absent while their bound bodies stay byte-identical
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
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
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
  - tests/copier-update.sh
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
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan; checked Plan 246 owns the bound construction text
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 247 must not resume until this plan is checked
checked_summary_ja: 事前スキーマ構築が到達不能な分岐や未呼出関数に置かれた場合を拒否し、bodyの一致だけで通らないようにする。

## Decisions

- Close the residual boundary checked Plan 246 recorded rather than restate it. Binding the construction text proves the bytes are present; it proves nothing about the files being created.
- Place the reachability refusal in the validator, which already reports an unreachable inventory copy and staging region, so the checker keeps one reachability model rather than two.
- Reject both spellings the review reproduced: a never-taken branch around the construction span, and a function that carries the span with no call site.
- Limit the implementation to the existing shared graph's reachability facts for the three bound construction spans. Do not add sourced-command, command-lookup, environment, or dynamic-dispatch proof.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [ ] Reproduce the admission read-only by wrapping the pre-schema construction span in `if false; then` and `fi`, and again in an uncalled function, and confirming the committed gate accepts both.
- [ ] Report a bound construction whose enclosing command list is skippable, and keep the committed fixture accepted unchanged.
- [ ] Add mutation coverage for the never-taken branch, for the uncalled function, and for each of the three bound constructions.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded as Medium finding 3 of the Plan 247 independent review, matches the residual boundary checked Plan 246 recorded, and was confirmed in the main session against the committed gate with `tests/copier-update.sh` left byte-identical.
- Plan 261's shelved full dispatch proof does not affect this plan. The required reachability fact is already represented in the shared graph and does not require external command resolution.
