# Authorize verify-copier-update plan validation

status: checked
primary_invariant: admit exactly the root repository verify-copier-update test command required by Plan 119 without widening generated-project validation authority
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: no
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
  - docs/plan/checked/2026/08/16-31/122-integrate-bounded-repair-lifecycle.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Permit only `python3 tests/test-verify-copier-update.py` with no additional arguments in the root plan-validation allowlist.
  - Keep the generated-project plan-validation allowlist unchanged and deterministically reject this root-only test command there.
  - Preserve every Plan 119 acceptance item, accepted Copier safety condition, write scope, validation authority outside this one root command, and external-effect authorization.
  - Finish with zero unresolved High or Medium independent-review findings and pass the focused validation before Plan 119 resumes through a fresh execution run.
repair_source: docs/plan/active/119-integrate-verify-copier-update-skill.md
repair_reason: the prior authoritative run could not authorize the root-only verify-copier-update test command recorded in Plan 119 validation
checked_summary_ja: Plan 119で必要なroot専用Copier検証テストだけをplan検証コマンドとして許可する。

## Decisions

- Admit the already-preserved two-file repair; do not modify the Copier helper, generated validator, Plan 119 acceptance, or security policy.
- Require an explicit generated-validator rejection assertion in addition to the root acceptance assertion.
- Use bounded parent implementation because the repair changes validation authority, with one independent read-only review before validation.

## Tasks

- [x] Add the generated-validator rejection assertion for the root-only command.
- [x] Confirm the preserved allowlist entry has no alternate arguments or prefixes.
- [x] Complete independent review and focused validation with zero unresolved High or Medium findings.
- [x] Archive and commit this repair before returning Plan 119 to `in_progress` with a fresh execution identity.

## Validation Notes

- Plan 122 is checked; Plan 119 remains deferred and has no replan contract.
- The repair bytes were preserved in stash `56d8f1766287e87a9f19a997318996c1f9dc8dc6` and restored without dropping that recovery point.
- The initial plan command attempted to execute a package module directly and failed before testing; the plan now uses the repository's existing `tests/test-validation-tools.py` entrypoint and a fresh execution identity.
- Independent read-only review reported High 0 and Medium 0; probes accepted only the exact root argv and rejected additional arguments, alternate launchers, shell forms, and every generated-validator form.
- Focused validation passed `python3 tests/test-validation-tools.py` (31 tests) and the scoped diff check.
- Final validation passed the same 31 tests, root policy check, full change validation, and `git diff --check`.
