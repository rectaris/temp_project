# Admit the compile checks the change-aware selector emits for a generated project's own source roots

status: backlog
primary_invariant: Every py_compile command the change-aware selector emits for a changed repository file is a command the validation allowlist admits.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The shipped is_python_compile refuses python3 -m py_compile src/build/lookup.py, while select_commands in the shipped validate-changes.py emits exactly that command for a changed src file, so the run aborts with ValidationCommandError.","kind":"reproduced_defect"}
  - {"evidence":"The repository's own scripts/plan_validation_commands.py already admits a wider root set than the shipped copy, so widening admission while keeping the containment checks follows a form this repository already ships.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/plan.py already drives parse_validation_command against both the root and the shipped module, and tests/validation_tools/changes.py already loads the selector through load_selector.","kind":"existing_mechanism"}
completion_conditions:
  - A changed Python file under a source root the template does not enumerate is admitted as a compile check instead of aborting change-aware validation.
  - An absolute path, a parent-directory escape, and a non-.py argument stay refused as compile checks.
  - A compile command the change-aware selector can emit but the allowlist refuses fails a test.
completion_witness_map:
  - {"condition_sha256":"sha256:246c626a3b51c37290f72241b3628356721f430a47309dc4fa0babb1943bd433","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:75fd861f495dafbc5cb73de3f4f69ee86fa42f0b23bb08a39ddff5ca3200a0f0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:53be7d15529040bb305cc6347cd2271dd7b7714cab7123134e9f3ed26e56f594","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/changes.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/plan_validation_commands.py
required_specs:
  - template/.project-agent-workflow/docs/agent/SPEC_VALIDATION.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
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
  - The two sides can no longer disagree without a test failing, because the guard derives the selector's emission rather than restating it.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:80a7adb7b64fe34b829634b347e9f95384c660702c7d670b166c0885c4e19c43","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:92d5637655ae0098dee5a5dad78e5682a4138ef71a1844d2df4f4c8f362e755c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:a33ea5beb12d40b6d46ead159126d5582281fc8050b27e49f9c79c95db63e729","authoritative_only_reason":"Change-aware validation runs against a generated project tree that only the Copier fixture builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:91947e124e4cd4ce4c2b2e9fd9aa104cad27d14f65660f97e087e9579ea0e697","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 変更対応検証が選ぶコンパイル確認を、生成先プロジェクト自身のソース配置でも許可する。

## Decisions

- Widen the shipped allowlist to accept any contained repository-relative .py path rather than adding src to the literal root set. A generated project may keep its sources under app, lib, pkg, or any other root, so a second literal list fails the next project the same way.
- Keep every containment check unchanged. Admission still refuses an absolute path, a parent-directory escape, and a non-.py suffix, and those checks are what bound the command.
- Treat py_compile as compile-only. It does not import the named module, so restricting which repository root a contained path sits under adds no execution boundary and only encodes the template repository's own layout.
- Derive the drift guard from the selector in validate-changes.py rather than restating its selection rules in the test. A hand-written second list is what produced this defect.
- Leave the repository's own scripts/plan_validation_commands.py unchanged. Its reconstructed-plan clauses serve this repository and are outside the defect, which only reaches generated projects.

## Tasks

- [ ] Widen is_python_compile in the shipped plan_validation_commands so a contained repository-relative Python path is admitted regardless of its root.
- [ ] Add a test that a changed Python file under a source root the template does not enumerate is admitted as a compile check.
- [ ] Add a test that the containment refusals still hold for an absolute path, a parent-directory escape, and a non-.py argument.
- [ ] Add a guard that derives the selector's compile emission from validate-changes.py and asserts the allowlist admits it.
- [ ] Run the declared validation commands.

## Validation Notes
