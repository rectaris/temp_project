# Use the selected current files for every generated-project smoke copy

status: in_progress
primary_invariant: Every smoke copy uses the same explicitly selected source and ref; the default isolated source reflects current Copier input files without mutating the original checkout.
task_types:
  - template_workflow
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At f07616d, the unchanged tests/smoke.sh preparation block exits 0 after an isolated edit to template/.project-agent-workflow/scripts/tool_command_context.py, but its render-source file still equals the old commit. See the dated investigation report.","kind":"reproduced_defect"}
  - {"evidence":"tests/smoke.sh already creates a disposable clone and a local candidate commit. Copier inputs live in template/, copier.yml and scripts/; Git can enumerate their tracked and nonignored files without maintaining two file lists.","kind":"existing_mechanism"}
completion_conditions:
  - With no COPIER_SMOKE_REF, the isolated source includes staged and unstaged bytes, nonignored new files, tracked deletions and executable modes within copier.yml, template/ and scripts/.
  - Successful copies and invalid-answer copies use the same prepared source and ref; an explicit COPIER_SMOKE_REF uses that committed revision without current-file overlay.
  - Preparation leaves source HEAD, refs, index and working files unchanged, does not overlay ignored artifacts or paths outside the declared input boundary, and fails before Copier starts on unsupported or unreadable input.
completion_witness_map:
  - {"condition_sha256":"sha256:59199e0aedacaa22bbf1b4aeec14d77f9ed5be09aa515c3a5d715b68164678f5","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ebf7b6f869c507067860364767101c99dcbd3a7e938955bf7f3804de34ed9d71","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:38ef5cb86ea963db5a9599b8814dbeb4b314f39fe2b2e264921e5ca8f01ba871","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - tests/smoke.sh
  - tests/prepare-smoke-source.py
  - tests/validation_tools/smoke_source.py
  - tests/test-validation-tools.py
  - scripts/project_workflow/copier_inventory.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - tests/lib-copier.sh
  - copier.yml
  - docs/plan/checked/2026/09/01-15/305-make-test-fixtures-independent-of-host-state.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - With no COPIER_SMOKE_REF, the isolated source includes staged and unstaged bytes, nonignored new files, tracked deletions and executable modes within copier.yml, template/ and scripts/.
  - Successful copies and invalid-answer copies use the same prepared source and ref; an explicit COPIER_SMOKE_REF uses that committed revision without current-file overlay.
  - Preparation leaves source HEAD, refs, index and working files unchanged, does not overlay ignored artifacts or paths outside the declared input boundary, and fails before Copier starts on unsupported or unreadable input.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:59199e0aedacaa22bbf1b4aeec14d77f9ed5be09aa515c3a5d715b68164678f5","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:ebf7b6f869c507067860364767101c99dcbd3a7e938955bf7f3804de34ed9d71","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:38ef5cb86ea963db5a9599b8814dbeb4b314f39fe2b2e264921e5ca8f01ba871","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Select this backlog plan for implementation, publish its active bytes, and prepare its exact plan-bound worktree before product edits.
  - Use parent-owned implementation and independent read-only review because the scope includes test registration or validation tooling. Preserve existing review budgets and all acceptance gates.
  - Execute serially. These plans share the validation test entrypoint; do not enroll them as an independent parallel group.
checked_summary_ja: 生成テストが未コミットの変更も含む同じ入力を検査するようにする。

## Decisions

- Replace both manual copy/staging path lists with one root-test helper. Enumerate Git-tracked inputs plus nonignored new files only under copier.yml, template/ and scripts/, using NUL-delimited paths. Do not copy the repository home, .git configuration, ignored logs, caches or credentials.
- Materialize deletions and current regular-file bytes/modes into a fresh --no-hardlinks clone. Use clone-local Git identity and stage only the helper-selected paths there. Reject symlinks and unsupported file types in the selected input set rather than following them; repository inputs currently require no symlink support.
- Select the source once and reuse it for render_fixture, default-copy paths and invalid-answer checks. Preserve the explicit-ref path and existing smoke assertions, REQUIRE_COPIER and REQUIRE_ACTIONLINT behavior.
- Keep this root-only test infrastructure out of generated projects. Register the helper and test module in the existing root inventory and aggregate test entrypoint; no generated validation policy or new release tag is changed.
- Do not create a new snapshot authority, execution ledger, release process or reusable skill. A local test-source preparation helper is sufficient.

## Tasks

- [ ] Add SmokeSourceTest in tests/validation_tools/smoke_source.py and import it from tests/test-validation-tools.py. Register new Python files in scripts/project_workflow/copier_inventory.py.
- [ ] Reproduce an edit to template/.project-agent-workflow/scripts/tool_command_context.py absent from the old lists; require the prepared clone to contain the edited bytes, not the old committed bytes. Cover an edited copy-task script under scripts/ as a second case.
- [ ] Cover staged plus later unstaged changes to one file, a new nonignored template file, a deletion, a path containing spaces, and an executable-bit change. Assert the original source HEAD, refs, index digest and worktree snapshot remain unchanged.
- [ ] Cover ignored local evidence, an untracked file outside the selected prefixes, unreadable input via controlled fault injection, and symlink/special-file refusal. Initialize disposable repositories with their own Git identity.
- [ ] Implement the helper and route all copy paths through the same source/ref selection. Add subprocess argument-capture tests for ordinary and invalid-answer copy functions; assert explicit-ref selection bypasses the overlay.
- [ ] Review the input boundary and registered tests, then run focused validation and the mandatory suite. Require a real Copier for the implementation smoke run and record the selected source mode with the results.

## Validation Notes

- Planning baseline: f07616d02f8db6c6df55c2fa6dfedfd046e87c4f in temp_project.
- Owner instruction: これまでのこのプロジェクトでの開発作業について改善できる部分を探し、改善するためのプランとして作成せよ。
- This task authorizes plan authoring only. No implementation, stopped-run continuation, remote publication or performance claim is included.
- Planning evidence and reproduction steps: docs/plan/development-improvements-20260912.md. Regression assertions described here must be added and exercised during implementation; their future success is not claimed now.
