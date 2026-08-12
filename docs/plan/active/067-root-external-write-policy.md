# Activate task-scoped external writes in the root repository

status: in_progress
task_types:
  - planning_docs
  - security
  - skill_authoring
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - CHANGELOG.md
  - docs/agent/
  - docs/plan/
  - scripts/
  - tests/test-validation-tools.py
context_files:
  - AGENTS.md
  - .codex/skills/mcp-ops/SKILL.md
  - copier.yml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/plan/checked/2026/08/01-15/065-task-scoped-external-access.md
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - template/.project-agent-workflow/scripts/check-external-service-policy.py
  - template/.project-agent-workflow/skills/mcp-ops/SKILL.md
  - template/docs/agent/external-services.yaml.jinja
  - .agent-artifacts/referent-contracts/root-external-write-plan/contract.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-external-service-policy.py check
  - python3 scripts/check-root-agent-policy.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Use directory-prefix sandbox mounts only because the root policy and checker entrypoint are new files; reject a candidate patch that changes docs/agent or scripts paths other than docs/agent/SPEC_EXTERNAL_SERVICES.md, docs/agent/external-services.yaml, docs/agent/spec-index.yaml, scripts/check-external-service-policy.py, scripts/check-root-agent-policy.py, and scripts/lint-project-workflow.sh.
  - Add a root-owned schema version 2 policy at docs/agent/external-services.yaml with access_profile task_scoped_default_allow, a GitHub fallback, no credential material, and the protected and denied effects accepted by plan 065.
  - Add a root normative specification at docs/agent/SPEC_EXTERNAL_SERVICES.md that defines the active root policy, keeps provider configuration separate from authorization, and requires a fresh check for each exact provider operation, target, effect set, and payload.
  - Add scripts/check-external-service-policy.py as a small root entrypoint that invokes the maintained template checker implementation with the root policy explicitly selected; do not duplicate the checker logic or treat a Jinja template as runtime policy.
  - Make the paths already required by the root mcp-ops Skill executable without weakening its fail-closed behavior when policy, provider configuration, task relevance, target, effect classification, or confirmation is missing.
  - Authorize a task-required ordinary read or write only when the active environment confirms that the exact provider is configured and authenticated and the current user request requires the exact operation, target, and ordinary effect.
  - Require matching current-user confirmation for remote_delete, public_communication, financial_commitment, production_change, access_control_change, and every unclassified write; reject missing, mismatched, or incomplete target and effect confirmation.
  - Reject credential_material_transfer, secret_persistence, and write_credentials_to_untrusted_code even when task relevance and confirmation are present, and reject ordinary when combined with another effect.
  - Cover GitHub branch and tag pushes as ordinary writes and GitHub pull-request and Release publication as public_communication, without performing an external write in deterministic tests.
  - Treat the current release request as task authorization for rectaris/temp_project only after the implementation resolves each exact ref, tag, Release, and dev-to-main pull-request target and runs the matching policy check immediately before the provider call.
  - Route root external-service work through docs/agent/spec-index.yaml and add deterministic root checks that fail if the policy, specification, entrypoint, required effect boundaries, or maintained checker delegation disappears.
  - Keep copier.yml defaulting generated projects to restricted, keep existing project-owned policies update-safe, and leave the reusable template authorization behavior unchanged.
  - Record the corrected root authorization behavior in CHANGELOG.md and complete all required validation before any release, push, or public GitHub write resumes.
checked_summary_ja: temp_project ルートに task-scoped version 2 方針と検査入口を配線し、現在の依頼に必要な外部操作を効果別の境界付きで認可する。
## Context

Plan 065 implemented a selectable schema version 2 policy for Copier-generated projects but did not install an active policy, normative specification, or checker entrypoint for this template source repository.

The root `mcp-ops` Skill now requires those exact root paths, so every root external-provider operation fails before it can evaluate the accepted task-scoped authorization rules.

## Decisions

- Plan 066 is checked, and this plan resumes through the sandboxed runner with its bounded model fallback available.
- Use directory-prefix sandbox mounts for `docs/agent/` and `scripts/` because the runner cannot create a new exact-file target, then enforce the narrower intended file list during parent candidate review.
- Install a root-owned schema version 2 policy instead of reading Jinja template sources as runtime configuration.
- Keep project-specific policy values under `docs/agent/` and keep the reusable generated-project template default set to `restricted`.
- Reuse the maintained checker implementation through a root entrypoint that always selects the root policy.
- Apply the effect taxonomy and confirmation boundaries accepted by plan 065 without adding a GitHub-specific bypass.
- Classify branch and tag pushes as ordinary writes, and classify pull-request and GitHub Release publication as `public_communication`.
- Use the active user request as task authorization only for exact provider operations, targets, and effects resolved during that request.
- Keep actual external writes outside deterministic validation and resume the requested release workflow only after the root gate passes locally.

## Tasks

- [ ] Add the root version 2 policy and normative external-service specification.
- [ ] Add the root checker entrypoint and deterministic root policy checks.
- [ ] Add authorization tests for ordinary GitHub writes, confirmed publication, mismatched confirmation, denied effects, and missing runtime facts.
- [ ] Update root routing and the changelog without changing the reusable template default.
- [ ] Run every required validation command and record the results.
- [ ] Archive the completed plan before resuming release, tag, push, and pull-request publication.

## Validation Notes

- Pending implementation.
