# Name the one safe credential presence test in the security specification, and make change-aware validation scan changed shell files, and CI scan the same files, for the enumerated unsafe forms.

status: in_progress
implementation_mode: parent_direct
primary_invariant: A changed shell file carrying an enumerated direct-display form of a credential-named variable fails validation, both locally and in continuous integration.
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
  - {"evidence":"The security specification forbids printing credentials but names no safe way to test whether one is configured, so an agent chose a form that expands the value and printed a live bearer token.","kind":"reproduced_defect"}
  - {"evidence":"Running the bracket-test form with a fixed-literal alternate under bash established that it reports presence for a non-empty value and absence for an empty or unset value without expanding it, so the specification can name one exact safe form instead of describing it.","kind":"reproduced_defect"}
  - {"evidence":"select_commands in validate-changes.py adds the static security check only when a changed path starts with the workflows directory or the workflow scripts directory, and the generated continuous integration workflow runs validation in managed scope only, so an ordinary changed shell script is scanned by neither path today.","kind":"reproduced_defect"}
  - {"evidence":"security-static-check.py already applies compiled patterns from security_rules.py to every scanned file and already accepts a changed-file scope, so widening which changed paths select it reuses a mechanism that exists rather than adding one.","kind":"existing_mechanism"}
completion_conditions:
  - The security specification names one exact presence test that cannot expand a credential value, beside the existing prohibition, in both the root and generated copies.
  - A changed shell file outside the workflow directories selects the static security check locally.
  - Continuous integration scans the same changed shell files rather than only the managed scope.
  - A scanned shell file carrying an enumerated direct-display form of a credential-named variable fails the check, and one carrying only the safe presence form passes.
  - Documentation and test text that must quote the unsafe form is exempt by a declared mechanism rather than by scan scope.
completion_witness_map:
  - {"condition_sha256":"sha256:59340021331e53c0e3f82f3ef1b447a6f00c09080795c2a10671705edece8b8b","witness":"scripts/lint-project-workflow.sh"}
  - {"condition_sha256":"sha256:2865cc8f40db902c5fe0bdabe64bf1a02e9c4f8a7bb92e8ea23ba4b926d3614d","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:29d999ae611d8784364ab533127f459f1a53a450754d8e986ad16adc71038b94","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ae90670dc685b01cbe3d8c5da02f75efd2113f0528db888d9572329e8434fd3a","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f85bd03bfc26f637f1d8fd6a58f4c8cd4380c486e48087a6eb64adee2b73c9f3","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/scripts/security-static-check.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - template/.github/workflows/project-agent-workflow.yml
  - tests/validation_tools/generated.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/.project-agent-workflow/scripts/security_rules.py
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
required_specs:
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - scripts/lint-project-workflow.sh
  - python3 tests/test-validation-tools.py
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The specification states the exact safe presence form and why the default operator is unsafe, in both the root and generated copies.
  - A changed ordinary shell script selects the static security check, which no current selector rule does.
  - Continuous integration scans a changed ordinary shell script against the merge base rather than only the managed scope.
  - A scanned shell file carrying the unsafe form fails the check, and one carrying only the safe presence form passes.
  - A Python file that reads a credential from the environment for legitimate use does not fail the check.
  - Documentation and test fixtures that quote the unsafe form are exempt by a declared mechanism, and an exempt file passes while a non-exempt file with the same bytes fails.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:819f78c1432632a3eeb8cd54f3b2e581906523968212fee0885aff536cb6b9eb","stage":"focused","witness":"scripts/lint-project-workflow.sh"}
  - {"acceptance_sha256":"sha256:128425ab4c5bf3a6fb9c31cb377f6b18432b474296c3d22e4b93a0f24acc345a","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:70c580413d588921cbefbfb61a5bc21f54df3051700d4ab4b57da25827e304ae","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:c1e42eecc4f09be581c2e600b1517b68e01f39daf2e59dba0df668d21bc5682d","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:e9a52e6ceee0937e63e6e4f5e7677fb03202e04575f40254331a592c9a1170d3","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:457cd5a48ab8b54911383ab1976cb16e81d2580922ea0a4fdb5f8ee5b5164ea4","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 認証情報の存在確認の安全な書き方を仕様に明記し、変更されたシェルスクリプトを静的検査と CI の対象に加える。

## Decisions

- Depend on the gate plan for the credential-name classifier rather than duplicating it, because two copies of a security classifier drift, and the gate is the surface that actually prevents the incident.
- Share the credential-name classifier only, and write a separate rule for shell file contents, because the gate inspects one command string while this check inspects whole files, so the same command-shape pattern is not meaningful in both places.
- Scope the file scan to shell files rather than also Python files, because a Python file that reads a credential from the environment is doing legitimate work and a byte-level rule cannot tell that from disclosure without a sink analysis this plan does not attempt.
- Widen continuous integration as well as the local selector, because the generated workflow runs the managed scope only, so widening the local selector alone would leave the invariant unenforced where it matters most.
- Put the safe form beside the existing prohibition rather than in a new section, because the reader who reaches the prohibition is exactly the reader who needs the alternative.
- Measure the widened rule against this repository before fixing its shape, because if it matches many existing files the honest response is to narrow the rule, not to carve out exceptions after the fact.
- Treat this scan as defence in depth. It reads committed bytes and cannot see the throwaway command that caused the incident; the gate plan owns that boundary.

## Tasks

- [ ] Confirm the shared credential-name classifier exists in the security rules module before starting, because this plan consumes it and must not restate it. If it is absent, stop: the gate plan has not landed.
- [ ] Add the exact safe presence form to the secrets section of the security specification, beside the existing prohibition, and state why the default operator is unsafe. Mirror the same text into the generated specification.
- [ ] Write a shell-file rule in the static security check that imports the shared credential-name classifier and applies its own file-content pattern. Do not reuse the gate's command-string pattern, and do not scan Python files with it.
- [ ] Widen the change-aware selector so a changed shell file anywhere in the repository selects the static security check, not only a changed workflow or workflow-script path.
- [ ] Make the generated continuous integration workflow scan the pull request's changed files against the merge base, so the widened selector takes effect there and not only in a working tree with uncommitted edits.
- [ ] Declare an exemption mechanism for files that must quote the unsafe form, cover documentation and test fixtures, and add a test that proves an exempt file passes and a non-exempt file with the same bytes fails.
- [ ] Before fixing the rule's shape, run it over this repository's existing shell files and record the result. Fix real findings; if the match count shows the rule is too broad, narrow the rule and record that instead of adding exceptions.

## Validation Notes

- Baseline recorded before implementation: tests/test-validation-tools.py passes on the unchanged checkout, and the count of existing shell files matching the proposed rule is recorded before the rule is fixed.
- Ordering: this plan consumes the credential-name classifier defined by the gate plan. The workflow has no machine-checked predecessor field, so the first task verifies the classifier exists and stops if it does not.
- Coverage boundary: this plan scans changed shell files. It does not scan untouched history, it does not scan Python files, and it cannot see a command that is never committed.
