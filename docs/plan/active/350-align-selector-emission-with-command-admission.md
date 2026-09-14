# Align the change-aware selector's emission with the commands it is allowed to run

status: in_progress
implementation_mode: parent_direct
primary_invariant: The change-aware selector validates its own selection as structured argv and emits only compile targets that resolve inside the repository, so every command it emits for a changed file is both admitted and actually run as a check.
replan_sources:
  - docs/plan/active/343-admit-project-source-compile-checks.md
replan_contract: docs/plan/replanned/contracts/343-admit-project-source-compile-checks.json
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/349-complete-root-agnostic-compile-admission.md
integration_gates:
  - This plan proves the widened admission from plan 349 and the selector-side agreement together against every source acceptance item.
successor_plans:
  - docs/plan/active/349-complete-root-agnostic-compile-admission.md
  - docs/plan/active/350-align-selector-emission-with-command-admission.md
inherited_acceptance_digests:
  - sha256:80a7adb7b64fe34b829634b347e9f95384c660702c7d670b166c0885c4e19c43
  - sha256:92d5637655ae0098dee5a5dad78e5682a4138ef71a1844d2df4f4c8f362e755c
  - sha256:a33ea5beb12d40b6d46ead159126d5582281fc8050b27e49f9c79c95db63e729
  - sha256:91947e124e4cd4ce4c2b2e9fd9aa104cad27d14f65660f97e087e9579ea0e697
integration_source_ids:
  - 343
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"validate_selected_commands rebuilds its own argv through shlex.join and revalidates the string, so a changed file named 'src/a b.py' aborts on an unsupported quote and 'src/a$HOME.py' aborts on a shell metacharacter, although the command is executed without a shell."}
  - {"kind":"reproduced_defect","evidence":"python3 -m py_compile -q.py exits 2 with an argparse error on Python 3.12.3 instead of compiling, while ./-q.py compiles and exits 0, so a root-level hyphen name is admitted but never checked."}
  - {"kind":"reproduced_defect","evidence":"The lexical containment check admits a relative path that is a symlink to a file outside the repository, and py_compile follows it and reports the offending source line."}
  - {"kind":"existing_mechanism","evidence":"plan_validation_commands.validate_argv already accepts a structured argv tuple, so the selector can validate its own selection without converting it back into a shell command string."}
completion_conditions:
  - The selector validates its own selection as structured argv, so a changed Python file whose name contains a space or a dollar sign is compiled instead of aborting the run.
  - A changed Python file at the repository root whose name begins with a hyphen is emitted in a form py_compile treats as a filename rather than an option.
  - A compile target whose resolved location falls outside the repository is not emitted as a compile check.
  - A guard derives the selector's emission and fails when any reassignment, filter, or iterable substitution removes a changed Python file from it.
completion_witness_map:
  - {"condition_sha256":"sha256:8c60654b19a7345670d7a05ec38a6d2c98c41701345b9ad656c5b9f35d62c3c8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:6c1398b1a663b4092c841370fcbb2c44a5b8fa7940450630df300a2a3015c075","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:b083bbebc642ecffa6a4112294c659bb4988298bfec0e34d9784d8becf429e82","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:dbb4e3d859115fabca113cbc6d25fbfeade5a3be62fea290c8a005c52fee3484","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - template/.project-agent-workflow/scripts/validate-changes.py
  - tests/test-validation-tools.py
  - tests/validation_tools/selector_agreement.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/validation_tools/support.py
  - tests/validation_tools/changes.py
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
  - The two sides can no longer disagree without a test failing, because the guard derives the selector's emission rather than restating it.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:80a7adb7b64fe34b829634b347e9f95384c660702c7d670b166c0885c4e19c43","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:92d5637655ae0098dee5a5dad78e5682a4138ef71a1844d2df4f4c8f362e755c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:a33ea5beb12d40b6d46ead159126d5582281fc8050b27e49f9c79c95db63e729","authoritative_only_reason":"Change-aware validation runs against a generated project tree that only the Copier fixture builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:91947e124e4cd4ce4c2b2e9fd9aa104cad27d14f65660f97e087e9579ea0e697","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 変更対応検証のコマンド選択と許可判定を一致させ、選ばれた確認が実際に走るようにする。

## Decisions

- Validate the selector's own selection as structured argv through validate_argv instead of rebuilding a shell command string with shlex.join. The rebuilt string is checked against restrictions written for hand-authored plan commands, which is why a valid Git path containing a space or a dollar sign aborts a run whose command never reaches a shell.
- Emit a root-level path in ./ form so py_compile reads it as a filename. A root-level name beginning with a hyphen otherwise reaches argparse as an option, and the admitted command exits 2 without checking anything.
- Resolve each compile target and drop the ones that land outside the repository. Lexical containment cannot see a symlink, so it is not by itself the boundary that the source plan's decisions claimed it was.
- Own the agreement guard in this plan's own test module rather than editing the guard plan 349 ships. The two plans keep disjoint write scopes, and this module is where the combined behaviour of both sides is proved.
- Keep this plan's scope to the compile path the source acceptance names. Widening shell syntax checks to the same root-agnostic rule is separately authorized work and is not admitted here, because a successor may not add a requirement the source plan never carried.

## Tasks

- [ ] Replace the shlex.join round trip in validate_selected_commands with structured argv validation through plan_validation_commands.validate_argv, keeping the raw command text only for reporting.
- [ ] Emit compile targets in a form py_compile treats as filenames, so a root-level name beginning with a hyphen is checked rather than parsed as an option.
- [ ] Drop a compile target whose resolved location falls outside the repository, and record why lexical containment alone does not decide this.
- [ ] Add tests/validation_tools/selector_agreement.py with a guard that derives the selector's compile emission and fails on any reassignment, filter, or iterable substitution that removes a changed Python file from it.
- [ ] Cover a changed file name containing a space, a dollar sign, a leading hyphen at the repository root, and a symlink that escapes the repository.
- [ ] Register the new test module in tests/test-validation-tools.py.
- [ ] Run the declared validation commands and confirm both sides of the source acceptance together.

## Validation Notes
