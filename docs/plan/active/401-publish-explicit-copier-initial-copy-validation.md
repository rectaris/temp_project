# Separate explicit initial-copy validation from fail-closed updates

status: in_progress
primary_invariant: Only an explicitly requested fresh non-Git Copier copy may omit committed ownership checks after strict absence proof; ordinary and before-update validation require the exact-root repository, and later Git errors, reserved metadata or unknown observations never waive preservation checks.
task_types:
  - template_workflow
  - planning_docs
  - security
  - task_worktrees
  - external_services
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan388 focused real Copier update exited1 when the existing initial-copy validator rejected a filesystem-boundary absence frame. A bounded offline query reproduced the public refusal; the accepted explicit-copy path returns false while default update still refuses.","kind":"reproduced_defect"}
  - {"evidence":"Accepted b70fed245b4c45a244015bec88b4e3add2ebe440 supplies strict explicit initial_copy classification, its consuming boolean/CLI modes, four caller migrations and semantic regression cases. Independent source diagnosis confirmed the seven-path dependency boundary.","kind":"existing_mechanism"}
  - {"evidence":"Public validators are exact mirrored stdlib scripts with an existing ownership pin and existing full migration/Copier suites. Adapt only the selected fix and tests to existing subprocess fixtures; retain public inventory bytes and avoid the absent _local_processes helper.","kind":"mechanical_transformation"}
completion_conditions:
  - Actual CLI initial-copy mode accepts only a deliberately selected fresh Git-less destination with strict absence evidence; default and pre-update modes still refuse absent, ambiguous or wrong-root repository state, and existing metadata or a later Git failure cannot exempt ownership checks.
  - The root and identical installed validators, four initial-copy fixture calls and documented commands consistently use explicit copy intent; supported real copies and updates retain project-owned artifacts, policy, rejection behavior and every unchanged mandatory validation command.
completion_witness_map:
  - {"condition_sha256":"sha256:ebf0f776fd9fc24db18801f141fa324d761ccae9f1357fd5cb0d7c59e8068ca3","witness":"python3 tests/test-copier-migration.py"}
  - {"condition_sha256":"sha256:795950a5146c2f99fb6a191569e7e28d2866fa9259d73444cd09db429d6ffcfe","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/copier-update.sh
  - tests/test-copier-migration.py
  - references/template-development.md
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - CHANGELOG.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/create-root-plan.py
  - scripts/project_workflow/plan_authoring.py
  - scripts/check-copier-template.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - copier.yml
  - docs/plan/active/388-publish-parent-held-git-input-foundation.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-copier-migration.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Explicit fresh-copy validation handles ordinary and canonical filesystem-boundary Git absence without accepting unknown or incomplete results; update paths retain exact-root, ownership and clean-start checks, and reserved or disappearing metadata cannot silently waive them.
  - Matched root/template implementations and actual generated copy/update consumers expose the same explicit mode and preserve existing project-owned content and refusal cases under the unchanged full suites; no missing helper, unrelated pin/history or operational adoption is introduced.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a97a5da292e4b9d56c8c42d02ec58cf9ef25b918cfdf171e9a3c54389c7d2db6","stage":"focused","witness":"python3 tests/test-copier-migration.py"}
  - {"acceptance_sha256":"sha256:f6b1343dc3af97e7d5b12b2d5d42a6a52c6b90cb5a656533ec6a942d28217827","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 初回コピーを明示し更新時のGit検査を免除しない

## Decisions

- Tier2 is a separate validation security-contract prerequisite, not a widened input-bundle candidate or a count-reset successor. Keep Plan388 and public418 deferred with all requirements, candidate bytes, original findings, unknown consumption and source478 refusal preserved.
- The actual owner selected necessary prerequisite PRs and explicitly authorized first public control-source migration. Parent performs this necessary distribution-validation prerequisite serially under the same first-installation boundary; no old execution or candidate control authorizes the work, and merge/operational adoption remain excluded.
- Port the accepted explicit initial_copy mode and strict absence/root/marker checks into public-base functions. Preserve the public ownership digest and all unrelated code. Default validation must not infer copy intent from a Git error; established Git state must still reach committed ownership inspection.
- Adapt semantic regression cases to the existing public subprocess/stdlib test harness rather than importing absent _local_processes or process_runtime. Remove only observed incidental value-copy tests, never a failing behavior test or an old safety case.
- Use the actual generated validator for all four initial-copy fixture validations, retain root/installed byte comparison, and preserve default update/before-update callers. No new question, backend, paid access, credential handling, execution authority or platform workaround is added.
- The goal is an independently accepted dedicated GitHub PR against dev after unchanged validation, managed local publication and fresh publication preflight. Publish only this prerequisite and its own necessary lifecycle history, not the held input-bundle product or unrelated private dev history.

## Tasks

- [ ] Publish this exact checked authored plan before implementation; keep every previously deferred item deferred.
- [ ] Port the explicit-copy producer and consumers in the exact mirrored scope, adapt meaningful regression coverage to the public harness, and prove the actual initial-copy success and default/update refusal before updating documentation.
- [ ] Update current root/generated explanations and changelog, then obtain independent exact-target clearance and run every declared focused and authoritative command unchanged in the task checkout locked environment.
- [ ] Commit and archive only on actual acceptance, publish the exact accepted tip locally with task checkout/branch absent, perform fresh GitHub startup/prepublication checks, push the scoped branch, create its PR and inspect real CI without merging.

## Validation Notes

- Private decision audit: pr-505-506-publication-20261028/copy-validation-prerequisite-decision-audit.txt. This addresses the independently confirmed pre-existing focused failure, not an authoritative failure and not a new policy/credential grant.
- Original failure: uv run --locked tests/copier-update.sh --require-copier, exit1; original output sha256:d6c07cd642048c5474d36056e817dd02aa88c54f842dd639a21790585478fe4d. Parent bounded reproduction and independent DiagnoseCopyRepository source assessment agree on explicit initial-copy versus update context as the one affected invariant.
- Accepted source b70fed2 uses a later test helper and a different ownership inventory pin; neither is a prerequisite of this port. Do not copy its historical audit or whole-file later history. Supplied old acceptance does not establish acceptance of this target.
- Plan388 corrected target caaaef703e99dfb9d3ec7f0c84b2065c2f915d796f7b1d1e06bddd28accec90d remains preserved in stash0515443366840b3e496284e1db361e8ab00c1ed3 and an external full patch, after requirement-preserving deferral commit665472b786c8cdd4a2a50e8f8e31172b21fe8910. Its product worktree/branch were retired; no product acceptance was claimed.
- Orca advisory coordinators have empty write scopes and their completed tabs are closed. Native reviewer outputs used for source assessment remain advisory, with unobserved session/model properties explicit; no fabricated legacy or schema8 formal receipt is admitted. Main owns every permission, scope, validation, lifecycle, commit and external effect.
