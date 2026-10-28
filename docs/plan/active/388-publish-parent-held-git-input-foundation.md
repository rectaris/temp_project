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
- Port only the existing accepted command/library family from local343dbbbe onto public b1eae00c. Do not copy unrelated intervening files or history. This is an input-materialization prerequisite, not the entire controller, PR intake, or an operational adoption.
- Candidate control runs only against declared offline fixtures until independent exact-target read-only assessment, unchanged mandatory validation and managed local publication accept this exact target. Candidate code never grants its own implementation or installation authority.
- Reuse semantic regression cases; enforce root/template byte and mode alignment in the production checker rather than retaining incidental file-equality or bare-help tests. Add one shared actual CLI behavior fixture for root, fresh generated and supported updated consumers.
- Keep full Git input inventory, parent manifest pin, same-operation recovery, retained unsafe states and explicit unverified runtime/native requirements. No secrets, paid access, credential changes, network operations or native member execution are added.
- The completion goal is a dedicated GitHub PR against dev after independent acceptance, managed local publication and fresh publication preflight. The owner authorized the necessary branch push and PR communication, not merge, release, public runtime adoption or PR24 changes.

## Tasks

- [ ] Publish this checked authored plan through its exact managed authoring task before product implementation.
- [ ] Port the accepted command and two libraries, register and mechanically align both distributions, retain meaningful regressions, and document actual capability and remaining execution boundaries.
- [ ] Add and exercise one actual CLI normal/corruption/nonexecution fixture across root, fresh generation and supported real updates without changing the required validation commands or weakening existing cases.
- [ ] Obtain independent exact-target clearance and run every focused and authoritative command unchanged in this task checkout's own locked environment; retain actual failures and diagnosis without inventing legacy or product review receipts.
- [ ] Accept and archive only on actual evidence, publish the exact accepted commit to its source branch with temporary task checkout/branch absent, then recheck and push the scoped branch, create its PR and inspect real CI without merging.

## Validation Notes

- Parent decision audit: external execution evidence pr-505-506-publication-20261028/first-public-installation-decision-audit.txt. Actual owner selections were 必要な先行基盤を分割してPR化 and 現行制御の初回移植も承認する; the latter explicitly excludes merge and operational adoption.
- The public baseline lacks the adopted execution policy; current-work returned exit1: current execution policy is missing; retained work grants no new authority. The new explicit first-installation authority is recorded separately; do not rerun that refusal, copy a policy to fabricate adoption or initialize a legacy execution.
- Private source policy necessity-1 pins controller7501ae6a; its acceptance and prior505/506 results do not transfer to this public target. Original public branch b1eae00c, local accepted source343dbbbe, original failed publication checks and unknown historical consumption remain distinct.
- Preserve the existing deferred public Plan418 and its index row. Orca helpers have empty write scopes and provide advisory source/CI mapping only; main owns permissions, authoring, implementation, review acceptance, validation, lifecycle, commits and external effects.
