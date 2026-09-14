# Make the shell syntax check admission root-agnostic and end a refused selection with a reason

status: backlog
primary_invariant: The command allowlist admits a contained repository-relative shell path as a syntax check regardless of which source root holds it, still refuses an absolute path, a parent-directory escape, and a non-.sh argument, and a refused selection ends change-aware validation with a stated reason rather than an unhandled traceback.
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
  - {"kind":"reproduced_defect","evidence":"The shipped is_script_syntax_check refuses sh -n tools/deploy.sh, while select_commands in the shipped validate-changes.py emits exactly that command for a changed tools/deploy.sh, so change-aware validation aborts on an ordinary shell script."}
  - {"kind":"reproduced_defect","evidence":"validate_selected_commands is called from main() without a handler, so the refusal above leaves the process through an unhandled ValidationCommandError traceback instead of a stated reason and exit status 1."}
  - {"kind":"existing_mechanism","evidence":"is_python_compile was widened to containment-only admission in the same module, so the same change to the shell rule follows a form this repository already ships and already tests."}
  - {"kind":"existing_mechanism","evidence":"tests/validation_tools/selector_agreement.py already compares the selector's emission rule against the allowlist's admission rule over a generated shape corpus, and already records this exact disagreement in test_a_shell_script_outside_the_enumerated_roots_still_disagrees."}
completion_conditions:
  - A changed shell script under a source root the template does not enumerate is admitted as a syntax check instead of aborting change-aware validation.
  - An absolute path, a parent-directory escape, and a non-.sh argument stay refused as syntax checks.
  - The selector's shell-file selection and the allowlist's syntax-check admission agree across the generated shape corpus, with no recorded exception left standing.
  - A command the allowlist refuses ends change-aware validation with a stated reason and exit status 1 rather than an unhandled traceback.
completion_witness_map:
  - {"condition_sha256":"sha256:5ba0c11c2791235556eb00be4ebfa9672114492aaf3b27572160e825c92dc7ff","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:10df56ac24f0b8f477e6de42b00fd9261a296e2ecc935b7bdf21f3e658bb6653","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:aa9f839887822cc86566292ff63041c09604dbdb110b71e5cbdf06a0eb5f4a68","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:545cfbc3cac778ef0b523e7e8c52fc259cea03dc353dd6a235a314ad9e017de4","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/plan_validation_commands.py
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - tests/validation_tools/changes.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/selector_agreement.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/plan/checked/2026/09/01-15/349-complete-root-agnostic-compile-admission.md
  - docs/plan/checked/2026/09/01-15/350-align-selector-emission-with-command-admission.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The root and generated allowlists admit sh -n and bash -n for a contained repository-relative shell path regardless of which source root holds it.
  - Both allowlists still refuse an absolute path, a parent-directory escape, and a non-.sh argument as a syntax check.
  - The selector's shell-file selection agrees with the allowlist's syntax-check admission across the generated shape corpus, and the test that recorded the disagreement asserts the agreement instead of being deleted.
  - A command the allowlist refuses ends change-aware validation with a stated reason and exit status 1 in both the plain and the JSON output mode.
  - Reverting the widened admission fails the test suite rather than passing on a corpus that happens to avoid the widened shapes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8f467621020d2d7fae5b194eeeed01f9ea19137b8a8f11ee960d36862fa04597","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:a9fb7c0696cadfbbf61b1aeb1b7a621e704981b256a298f849f5c57795d6daaa","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:4e9bb5f29a170b39aa0dd36ea685125506c7c250520fc2457222f6a982d67704","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:ee8057c5e702d8b8e157509b39d51626a070e0296f31a668d1877caeaaeddf5f","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:fc00bf925de57e9e2cd7fc3cb9d66ca8a2cff999a80c93d12013f9cf8b5c23ed","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: シェル構文検査の許可判定からディレクトリ名の制限を外し、選択処理と一致させ、拒否された選択を理由付きの失敗で終わらせる。

## Decisions

- Widen the shell rule the way the compile rule was widened, because both rules answer the same question and one of them has already been settled. Containment is the whole boundary: `sh -n` reads a file and reports syntax, so which repository root holds a contained path encodes one project's layout and nothing about safety.
- Keep the suffix restriction. The selector emits a syntax check for a changed `.sh` path only, so admitting a wider suffix set would break the agreement this plan exists to establish.
- Fix the unhandled refusal in the same plan rather than a later one. Widening admission removes the common way to reach the refusal, which would leave the remaining paths to it untested and their failure mode a traceback.
- Rewrite the recorded disagreement test rather than delete it. It names the exact gap this plan closes, so turning it into an agreement assertion keeps the evidence that the gap was closed on purpose.
- Change the root and generated copies together, because the repository's own alignment checks compare them and a one-sided change fails before the behavior can be judged.

## Tasks

- [ ] Record the baseline: run the suite unchanged, and record which shapes the selector emits that the allowlist refuses today.
- [ ] Widen `is_script_syntax_check` in the root allowlist to admit any contained repository-relative path with the `.sh` suffix, keeping the absolute, parent-directory and suffix refusals, and mirror the same change into the generated copy.
- [ ] Extend the allowlist tests so reverting the widening fails, and so an absolute path, a parent-directory escape and a non-.sh argument stay refused for both `sh -n` and `bash -n`.
- [ ] Rewrite `test_a_shell_script_outside_the_enumerated_roots_still_disagrees` to assert the agreement it previously recorded as a gap, and confirm the rule comparison in the same module still detects a narrowing of either side.
- [ ] End a refused selection in `main()` with a stated reason and exit status 1 in both the plain and the JSON output mode, in the root and generated copies, and add a test that drives that path.
- [ ] Run the whole selection corpus through the allowlist again and record any remaining disagreement instead of leaving it to a corpus that avoids it.

## Validation Notes

- Baseline to record before implementation: the shipped allowlist refuses `sh -n tools/deploy.sh`, which the shipped selector emits for a changed `tools/deploy.sh`, and the refusal leaves `main()` through an unhandled `ValidationCommandError`.
- Ordering: this plan follows the compile-side work, which settled the same question for `python3 -m py_compile`. The shell rule is the last enumerated-root restriction in the admission surface.
- Boundary: this plan changes which contained paths are admitted. It does not widen the accepted command heads, the accepted suffix, or the containment checks.
