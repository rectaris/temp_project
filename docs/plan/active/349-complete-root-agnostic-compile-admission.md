# Complete the root-agnostic compile admission in the generated command allowlist

status: in_progress
implementation_mode: parent_direct
primary_invariant: The generated command allowlist admits a contained repository-relative Python path as a compile check regardless of which source root holds it, and still refuses an absolute path, a parent-directory escape, and a non-.py argument.
replan_sources:
  - docs/plan/active/343-admit-project-source-compile-checks.md
replan_contract: docs/plan/replanned/contracts/343-admit-project-source-compile-checks.json
integration_gates:
  - Plan 350 proves this widened admission together with the selector-side agreement work against every source acceptance item before the source work counts as delivered.
successor_plans:
  - docs/plan/active/349-complete-root-agnostic-compile-admission.md
  - docs/plan/active/350-align-selector-emission-with-command-admission.md
inherited_acceptance_digests:
  - sha256:80a7adb7b64fe34b829634b347e9f95384c660702c7d670b166c0885c4e19c43
  - sha256:92d5637655ae0098dee5a5dad78e5682a4138ef71a1844d2df4f4c8f362e755c
  - sha256:a33ea5beb12d40b6d46ead159126d5582281fc8050b27e49f9c79c95db63e729
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"The shipped is_python_compile refuses python3 -m py_compile src/build/lookup.py, while select_commands in the shipped validate-changes.py emits exactly that command for a changed src file, so the run aborts with ValidationCommandError."}
  - {"kind":"existing_mechanism","evidence":"The repository's own scripts/plan_validation_commands.py already admits a wider root set than the shipped copy, so widening admission while keeping the containment checks follows a form this repository already ships."}
  - {"kind":"existing_mechanism","evidence":"tests/validation_tools/plan.py already drives parse_validation_command against both the root and the shipped module, and tests/validation_tools/changes.py already loads the selector through load_selector."}
  - {"kind":"reproduced_defect","evidence":"The drift guard added for the source plan reads only the first assignment to the emitted name, so inserting a later reassignment that filters the list passes the guard while removing a root from the emission."}
completion_conditions:
  - A changed Python file under a source root the template does not enumerate is admitted as a compile check instead of aborting change-aware validation.
  - An absolute path, a parent-directory escape, and a non-.py argument stay refused as compile checks.
  - Reverting the widened admission fails the test suite, and narrowing the selector's compile emission by reassigning its path list after the guarded comprehension also fails it.
completion_witness_map:
  - {"condition_sha256":"sha256:246c626a3b51c37290f72241b3628356721f430a47309dc4fa0babb1943bd433","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:75fd861f495dafbc5cb73de3f4f69ee86fa42f0b23bb08a39ddff5ca3200a0f0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:26b064e186ac0c184ee2e6a4c1248f7f21c6abcd511476532247e65517084f0c","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/changes.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/plan_validation_commands.py
  - docs/plan/checked/2026/08/16-31/125-authorize-generated-verify-helper-compilation.md
required_specs:
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Change-aware validation selects and runs a compile check for a changed Python file under a project source root the template does not enumerate.
  - The command allowlist keeps refusing an absolute path, a parent-directory escape, and a non-.py argument.
  - The generated-project fixture keeps passing with the widened compile admission.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:80a7adb7b64fe34b829634b347e9f95384c660702c7d670b166c0885c4e19c43","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:92d5637655ae0098dee5a5dad78e5682a4138ef71a1844d2df4f4c8f362e755c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:a33ea5beb12d40b6d46ead159126d5582281fc8050b27e49f9c79c95db63e729","authoritative_only_reason":"Change-aware validation runs against a generated project tree that only the Copier fixture builds.","stage":"authoritative","witness":"tests/smoke.sh"}
checked_summary_ja: 生成先の許可一覧が、ソース配置に依らず収まっている Python パスをコンパイル確認として受理するようにする。

## Decisions

- Widen the shipped allowlist to accept any contained repository-relative .py path rather than adding src to the literal root set. A generated project may keep its sources under app, lib, pkg, or any other root, so a second literal list fails the next project the same way.
- Keep every containment check unchanged at this layer. Admission still refuses an absolute path, a parent-directory escape, and a non-.py suffix. Filesystem containment is not admission's job and belongs to plan 350, which owns what the selector emits.
- Treat py_compile as compile-only. It does not import the named module, so restricting which repository root a contained path sits under adds no execution boundary and only encodes the template repository's own layout.
- Revoke the path-exact compilation boundary that plan 125 established, under the owner authorization recorded on 2026-09-14. Plan 125 admitted only the exact generated verify-copier-update helper path and kept every other generated Skill path unauthorized, which this admission cannot preserve.
- Repair the drift guard this plan ships rather than leaving a guard that its own author knows is bypassable. Plan 350 adds the authoritative agreement guard in its own module.
- Leave the repository's own scripts/plan_validation_commands.py unchanged. Its reconstructed-plan clauses serve this repository and are outside the defect, which only reaches generated projects.

## Tasks

- [ ] Widen is_python_compile in the shipped plan_validation_commands so a contained repository-relative Python path is admitted regardless of its root, and remove the literal generated-path set it replaces.
- [ ] Update the shipped module's own self-test so its negative cases exercise the surviving containment boundary and --self-test exits 0 inside the generated fixture.
- [ ] Add a test that a changed Python file under a source root the template does not enumerate is admitted as a compile check.
- [ ] Add a test that the containment refusals still hold for an absolute path, a parent-directory escape, and a non-.py argument.
- [ ] Repair the drift guard so a reassignment or filter applied to the emitted path list after its comprehension fails the guard.
- [ ] Run the declared validation commands.

## Validation Notes
