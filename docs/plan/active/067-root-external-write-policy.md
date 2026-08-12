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
  - Make the root entrypoint reject blank or whitespace-only operation and target values, and enforce the root GitHub operation-to-effect mapping for git.push, pull_request.publish, and release.publish before delegating to the maintained version 2 checker.
  - Make the paths already required by the root mcp-ops Skill executable without weakening its fail-closed behavior when policy, provider configuration, task relevance, target, effect classification, or confirmation is missing.
  - Authorize a task-required ordinary read or write only when the active environment confirms that the exact provider is configured and authenticated and the current user request requires the exact operation, target, and ordinary effect.
  - Require matching current-user confirmation for remote_delete, public_communication, financial_commitment, production_change, access_control_change, and every unclassified write; reject missing, mismatched, or incomplete target and effect confirmation.
  - Reject credential_material_transfer, secret_persistence, and write_credentials_to_untrusted_code even when task relevance and confirmation are present, and reject ordinary when combined with another effect.
  - Cover GitHub branch and tag pushes as ordinary writes and GitHub pull-request and Release publication as public_communication, without performing an external write in deterministic tests.
  - Reject pull_request.publish and release.publish when the caller declares ordinary alone, reject git.push when it declares public_communication, and reject malformed branch, tag, pull-request, or Release targets rather than trusting caller-supplied effect classification.
  - For the three known GitHub writes, accept only one exact target form per call: owner/repository:refs/heads/<branch> or owner/repository:refs/tags/<tag> for git.push, owner/repository:refs/heads/<head>->refs/heads/<base> for pull_request.publish, and owner/repository:release:<tag> for release.publish; do not accept an arbitrary nonblank resource as a Release or pull-request target.
  - Once the root entrypoint recognizes an authorize command, make any root parsing error fail closed instead of delegating an unvalidated request; add explicit negative tests for empty and whitespace-only operation and target values.
  - Prevent every argparse abbreviation or alternate spelling that could override the root entrypoint's fixed --policy argument, disable option abbreviation in root parsing, and make authorize help or unknown options return nonzero rather than look like successful authorization.
  - Use the single documented colon delimiter after owner/repository and validate branch and tag components with local git check-ref-format semantics; cover a valid plus sign and invalid trailing-dot ref component deterministically instead of maintaining a divergent handwritten ref grammar.
  - For git.push, pull_request.publish, and release.publish, require the provider name github and the exact repository rectaris/temp_project; reject a provider alias, typo, or another repository before generic checker delegation.
  - Pass the Git ref kind separately from the human-readable validation label so every pull-request head and base endpoint uses git check-ref-format --branch, while tag targets use the tag ref form; reject HEAD and leading-hyphen PR branch endpoints deterministically.
  - Reject option-like service and operation positionals before reconstructing delegated arguments, including `-- --help` and `-- -h`, so an escaped positional cannot become maintained-checker help with exit code zero.
  - Add separate negative fixtures for empty operation, whitespace-only operation, empty target, whitespace-only target, unknown authorize option, exact --policy, every accepted --policy abbreviation prefix such as --pol, authorize --help, and escaped positional help.
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
- Enforce the GitHub operations required by the current release workflow in the root entrypoint because the maintained generic checker intentionally cannot infer provider-specific effects from operation names.
- Use one canonical exact target form for each current release operation so the confirmation string and provider target cannot refer to different resources.
- Treat the fixed root policy path and successful root parsing as prerequisites to generic checker delegation; a usage/help response is not an authorization decision.
- Bind the three current release operations to the task-authorized provider and repository instead of inferring scope from a caller-supplied target string alone.
- Reconstruct only validated semantic arguments for delegation, and reject option-like positionals that would change meaning when the original `--` sentinel is removed.
- Classify branch and tag pushes as ordinary writes, and classify pull-request and GitHub Release publication as `public_communication`.
- Use the active user request as task authorization only for exact provider operations, targets, and effects resolved during that request.
- Keep actual external writes outside deterministic validation and resume the requested release workflow only after the root gate passes locally.

## Tasks

- [ ] Add the root version 2 policy and normative external-service specification.
- [ ] Add the root checker entrypoint and deterministic root policy checks.
- [ ] Enforce nonblank exact targets and the root GitHub release-operation effect map before generic checker delegation.
- [ ] Add authorization tests for ordinary GitHub writes, confirmed publication, mismatched confirmation, denied effects, and missing runtime facts.
- [ ] Update root routing and the changelog without changing the reusable template default.
- [ ] Run every required validation command and record the results.
- [ ] Archive the completed plan before resuming release, tag, push, and pull-request publication.

## Validation Notes

- Pending implementation.
