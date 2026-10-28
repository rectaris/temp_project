# Publish fixed accepted Git input bundles without execution authority

status: in_progress
primary_invariant: A parent-selected accepted Git commit and local publication ref produce one private, source-bound, tamper-evident input bundle; recovery never replaces unknown state, and materialization or a launch contract grants no execution, member admission, controller adoption, merge or historical acceptance.
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
  - {"evidence":"Accepted local tip343dbbbe contains the complete parent-authority wrapper, parent_authority library and its sole sibling dependency process_runtime; the libraries use only the Python standard library and fixed local Git object queries.","kind":"existing_mechanism"}
  - {"evidence":"The accepted ParentAuthorityTest supplies isolated Git repositories and source/tamper/recovery/placement/FIFO/process-bound counterexamples. Public b1eae00c already has its validation_tools.support loader and the same test aggregation convention.","kind":"existing_mechanism"}
  - {"evidence":"Public b1eae00c has checked plan authoring, source/generated inventories, mirrored helper alignment checks, fresh generation and a bounded real Copier update fixture. Port only this command family and its exact registrations, not intervening local history.","kind":"mechanical_transformation"}
  - {"evidence":"Accepted Copier product1c5a327a448b5eba2b43a33f62ff57b0a998d942 has explicit initial-copy validation and unchanged fail-closed updates; real generated copy/update passed and actual GitHub CI40683566160 succeeded in all six jobs. Its normally published checked Plan401 supplies the prerequisite record.","kind":"existing_mechanism"}
completion_conditions:
  - The actual CLI materializes and verifies exact accepted fixture blobs under one pinned manifest, rejects altered content while retaining it, and emits a fixed-input launch contract with execution_authorized and member_write_admitted both false.
  - Source/ref/repository mismatch, unaccepted inputs, unsafe paths or file types, changed bytes/modes, ambiguous or corrupted recovery and bounded child failures refuse without deleting or repairing unknown evidence; exact same-operation recovery preserves identity.
  - Root, fresh generated and supported Copier-updated distributions ship aligned command/library bytes and modes, expose the same actual fixed-input CLI behavior, and preserve project-owned product code, policy, configuration and mandatory validation.
completion_witness_map:
  - {"condition_sha256":"sha256:7050283e461bf7245c1c6ab7afc4b29d779745b0c86108febab02abe881398cd","witness":"python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py"}
  - {"condition_sha256":"sha256:f5ae9b2e3373bea627cd978b8dac529bbf20c76e00dd2ac7df6d882d634691b0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d5bf726bcaaf58d922f0e71cec2d6bc171202635e6fde6ef119abdabb8ea57af","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - scripts/parent-authority.py
  - scripts/project_workflow/parent_authority.py
  - scripts/project_workflow/process_runtime.py
  - template/.project-agent-workflow/scripts/parent-authority.py
  - template/.project-agent-workflow/scripts/parent_authority.py
  - template/.project-agent-workflow/scripts/process_runtime.py
  - tests/validation_tools/parent_authority.py
  - tests/test-validation-tools.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - CHANGELOG.md
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/parent-authority-cli.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/create-root-plan.py
  - scripts/project_workflow/plan_authoring.py
  - scripts/project_workflow/worktree_guard.py
  - docs/agent/git-retirement.yaml
  - docs/plan/checked/2026/10/16-31/401-publish-explicit-copier-initial-copy-validation.md
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
  - python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - One explicitly selected accepted Git commit/ref is materialized and verified as exact private inputs with a parent-pinned manifest; the actual CLI refuses corruption without changing retained bytes and never authorizes execution or member admission.
  - Existing meaningful source, placement, special-file, tamper, persistence, recovery and child-custody regressions pass on the public-base adaptation; no unknown evidence, legacy stop, unresolved finding or historical acceptance is rewritten or reset.
  - Actual fresh and supported updated CLI consumers preserve source-bound behavior, aligned root/template distribution and project-owned artifacts under unchanged mandatory suites; publication grants no operational controller adoption or merge authority.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5e3cba577126aec52606fc0c8785c65a78098870acacf940c7e00aaf3a566380","stage":"focused","witness":"python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py"}
  - {"acceptance_sha256":"sha256:6f6ef4beddef0bda4c72f05818f66544bb70f86b6424b16199c9ecf555ba71cb","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:010032a63d7f51d41c613cb80dc74b7b01ceafd2dfe545afbeaba424b37bcd38","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 受入済みGit入力を固定・照合する基盤を初回公開する

## Decisions

- Tier2 first public-source installation, parent-direct and serial, is expressly authorized by the owner's selection of 現行制御の初回移植も承認する. Preserve source478 and all existing executions; initialize no legacy execution or replacement genesis to reset authority or consumption.
- Port only the accepted command/library family from local343dbbbe onto the independently accepted Copier prerequisite and its normally published checked Plan401 metadata. Retain b1eae00c as the original public baseline. Copy no unrelated intervening files or history; this is neither the entire controller, PR intake nor operational adoption.
- Candidate control runs only against declared offline fixtures until independent exact-target read-only assessment, unchanged mandatory validation and managed local publication accept this exact target. Candidate code never grants its own implementation or installation authority.
- Reuse semantic regression cases; enforce root/template byte and mode alignment in the production checker rather than retaining incidental file-equality or bare-help tests. Add one shared actual CLI behavior fixture for root, fresh generated and supported updated consumers.
- Keep full Git input inventory, parent manifest pin, same-operation recovery, retained unsafe states and explicit unverified runtime/native requirements. No secrets, paid access, credential changes, network operations or native member execution are added.
- The completion goal is a dedicated GitHub PR against dev, where the owner has now merged prerequisite PR41. Reobserve exact base/head facts and run fresh startup/prepublication checks before every remote effect. Preserve the same repository, accepted product, requirements and external-effect authority; no future merge, release, controller adoption or PR24 change is authorized.
- Publish the independently accepted product with this plan still in_progress, create its PR and observe actual CI, then record and normally archive completion in a separately bound parent-owned lifecycle task under this existing Tier2 plan. Never mark future PR or CI work complete, or treat multi-file archival as Tier0.

## Tasks

- [ ] Publish this checked authored plan through its exact managed authoring task before product implementation.
- [ ] Port the accepted command and two libraries, register and mechanically align both distributions, retain meaningful regressions, and document actual capability and remaining execution boundaries.
- [ ] Add and exercise one actual CLI normal/corruption/nonexecution fixture across root, fresh generation and supported real updates without changing the required validation commands or weakening existing cases.
- [ ] Obtain independent exact-target clearance and run every focused and authoritative command unchanged in this task checkout's own locked environment; retain actual failures and diagnosis without inventing legacy or product review receipts.
- [ ] Accept and normally publish only the independently reviewed and validated product, remove its temporary task checkout/branch, recheck and push the scoped branch, create its PR and inspect actual CI, then record and normally publish archival under this Tier2 plan without any GitHub merge.

## Validation Notes

- Parent decision audit: external execution evidence pr-505-506-publication-20261028/first-public-installation-decision-audit.txt. Actual owner selections were 必要な先行基盤を分割してPR化 and 現行制御の初回移植も承認する; the latter explicitly excludes merge and operational adoption.
- The public baseline lacks the adopted execution policy; current-work returned exit1: current execution policy is missing; retained work grants no new authority. The new explicit first-installation authority is recorded separately; do not rerun that refusal, copy a policy to fabricate adoption or initialize a legacy execution.
- Private source policy necessity-1 pins controller7501ae6a; its acceptance and prior505/506 results do not transfer to this public target. Original public branch b1eae00c, local accepted source343dbbbe, original failed publication checks and unknown historical consumption remain distinct.
- Preserve the existing deferred public Plan418 and its index row. Orca helpers have empty write scopes and provide advisory source/CI mapping only; main owns permissions, authoring, implementation, review acceptance, validation, lifecycle, commits and external effects.
- Authored plan commit ac64f2278c7b06a7a368d7fa085453103439245e passed both unchanged prepublication commands in its own locked authoring checkout and was managed-published before implementation.
- Original target sha256:5aacbd018842240317c58f075f0b7a3e81fb32712ee2765b7dcab6d78f3660ca received one Medium source finding: a completed stage with its manifest could repair missing inventory. The parent reproduced missing-blob and missing-tree failures, corrected both mirrors within scope, and observed both refusal cases plus intact recovery passing. Fresh independent assessment cleared that finding on corrected target sha256:caaaef703e99dfb9d3ec7f0c84b2065c2f915d796f7b1d1e06bddd28accec90d; it did not accept the overall candidate.
- Declared focused root CLI and full validation-tools commands passed; real Copier update exited 1 at the pre-existing non-Git initial-copy validator. Original output sha256:d6c07cd642048c5474d36056e817dd02aa88c54f842dd639a21790585478fe4d and bounded diagnosis remain in external evidence pr-505-506-publication-20261028. No authoritative product command has run; no authoritative-failure state or legacy/schema-8 receipt is claimed.
- Independent source diagnosis confirmed the validator's fixed ordinary-diagnostic comparison rejects the host's filesystem-boundary absence frame. The existing accepted explicit-initial-copy mechanism can be ported independently, retaining default update rejection and every mandatory command. Its unrelated ownership pin, process helper and historical audit must not be copied into the port.
- Preserve the exact corrected candidate as local stash 0515443366840b3e496284e1db361e8ab00c1ed3 and external foundation-388-corrected-held-target.patch. This deferral changes no requirement, acceptance digest, product write scope or validation command and grants no new review capacity, adoption, or source478 authority.
- Prerequisite Plan401 was independently accepted, normally published and archived; PR41 was created without merging. Actual product-head CI40683566160 and archival-head CI40688994742 each completed successfully in all six jobs. Retain those exact head observations separately from any later publication state.
- Parent decision audit foundation388-pr-base-decision-audit.txt selects the preceding prerequisite branch as this PR's base while preserving the same repository, user requirements, safety conditions and external-effect authority. Use no historical count-only ceiling, old execution restart, replacement policy copying or candidate self-authorization.
- The installed creation check has no revision option or scope-candidates diagnostic and reserves a new identifier. This existing Plan388 revision instead uses the same accepted shared parse/build/symlink/index/render/report functions with identifier388, without reserving or creating another numbered plan. Preserve the original checked input and every held record.
- GitHub API observed rectaris merge PR41 at 2026-10-28T13:20:36Z; dev became cd7f81b46b0f1e5c9b3c7802ee8221bca47d29dd. Its tree 08a6c5a08f7a3b8e50b6b632a84fa3c5842f27aa exactly equals accepted prerequisite bb96f35f68796cb8715e7266c4a9e6c011dd1acd. Main performed no merge and infers no operational adoption. See copy401-observed-owner-merge-001.json and foundation388-owner-merge-publication-decision-audit.txt.
- Resumed product target sha256:2542c4b13f13b2dcf806ccd7f8defb545a8939c8ee9beb48754c89bb7fcac509 was independently source-reviewed on source53726981c6e74212f9b135ec96b94c326c98ce2a with plan digest sha256:d7b7eecc9deb6af538f38dca44791fef93918e936c720cd46a71bce8c71055e8. The actual native session was admitted once as canonical event124; source receipt sha256:1060d72e67d68cea656de042738f16360e78d61195bd860beea0dea43c9b21b7 reported no findings. Named-profile/provider-model and inheritance-hook proof remain unobserved; no normal schema8 receipt is claimed.
- All three declared focused commands passed on that exact target in its own locked checkout: actual root CLI1.32s, full validation-tools91.96s, and real Copier update126.78s. Unchanged authoritative lint-project-workflow.sh335.78s and tests/smoke.sh112.57s also exited0. Original mode-0600 captures and result files are foundation388-resumed-001-{focused,authoritative}-{N}.
- Accepted product commit402c708b3c00832f5ed93c517f9ffb4a888acd1e was normally published to refs/heads/rectaris/pr-parent-authority-foundation with its temporary plan branch and task checkout removed. Stash0515443366840b3e496284e1db361e8ab00c1ed3, both original findings and every failed attempt remain retained; publication of the input tool is not controller adoption.
- This checked publication-method revision changes no accepted product byte, requirement, safety condition, scope or validation authority. The old source assessment remains evidence bound to its actual original plan/source/target, never a formal receipt rebound to this revised plan digest. Before PR creation, fresh provider/base/head, full selected-diff, required-asset and disposable-application checks remain mandatory.
- The accepted owned reader refused current custody of the historical first parent-record original. Preserve it without chmod or copying it into admissibility; historical consumption remains unknown and no historical acceptance is inferred. The current explicit owner instruction, published plan and fresh independent product evidence are separate authority and evidence.
