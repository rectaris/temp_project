# Bind provider authentication to the external call execution context

status: replanned
task_types:
  - planning_docs
  - template_workflow
  - external_services
  - security
  - skill_authoring
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: ordinary
replan_reason_codes:
  - parent_remediation_budget_exhausted
write_scope:
  - .codex/skills/mcp-ops/
  - CHANGELOG.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - template/.project-agent-workflow/skills/mcp-ops/
  - tests/copier-update.sh
  - tests/fixtures/mcp-ops/
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/01-15/064-browser-task-routing.md
  - docs/plan/checked/2026/08/01-15/065-task-scoped-external-access.md
  - docs/plan/checked/2026/08/01-15/067-root-external-write-policy.md
  - template/docs/agent/external-services.yaml.jinja
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Define the provider-call execution context as the provider, command execution boundary, and credential source used for one exact external call.
  - Treat `runtime_configured` as satisfied only by configuration and authentication evidence obtained for the provider-call execution context that will perform the exact call; changing the provider, account, credential source, or command boundary invalidates that evidence and requires a new preflight and fresh authorization check.
  - Keep external-service policy schema version 2 unchanged, preserve existing project-owned version 1 and version 2 policies byte-for-byte through supported Copier updates, and do not persist host-specific sandbox or credential-store configuration.
  - Keep host approval to execute outside a sandbox separate from project authorization for the exact provider operation, target, and effect; require both when both apply, and never treat a saved command-prefix approval as external-write authorization.
  - When a minimal non-mutating authentication check fails only in the current sandbox while the user reports a valid login elsewhere, allow one approved check through the intended provider-call execution context before requesting reauthentication; if that check remains unavailable or inconclusive, fail closed and report the exact missing capability.
  - Distinguish inability to obtain credentials in one process environment, rejection of an authenticated account's provider permission, and absence of a configured backend; do not collapse these conditions into a generic login failure.
  - Do not reuse connector authentication evidence for GitHub CLI calls, GitHub CLI evidence for connectors, or browser session evidence for either; switching provider requires its own provider check and a fresh external-service authorization for the exact target and effect.
  - Keep retries non-mutating until the provider-call execution context is selected, prevent duplicate external writes with an exact remote-state read when the operation supports one, and never retry a protected write through another provider without current-task authorization and any required exact confirmation.
  - Permit diagnostics to report only sanitized provider availability, account identity when the provider exposes it safely, credential-source class, execution-boundary class, and error classification; never read, print, persist, or place token values or credential material in fixtures, policy, logs, or provider payloads.
  - Keep `mcp-ops` `SKILL.md` concise, place detailed execution-context and failure-routing guidance in one directly linked reference, and keep root and generated `SKILL.md`, reference, and `agents/openai.yaml` semantics aligned after path normalization.
  - Add the generated reference to managed inventories and prove fresh generation and non-destructive Copier update behavior without changing the discovery bridge trigger or introducing project-specific provider identities into generic template files.
  - Add structured median, edge, negative, and untuned holdout scenarios covering same-context success, sandbox-local credential lookup failure with approved host-context success, authenticated provider permission denial, provider or command-boundary change after preflight, unavailable fallback, duplicate-write prevention, and attempted credential persistence.
  - Validate every structured scenario's exact conditions and expected next action deterministically; keep live keyring access, live connector access, browser sessions, and external writes outside deterministic tests.
  - Run the system skill-creator structural validator for the root and generated `mcp-ops` skills when available, run all repository validation commands, and finish with zero unresolved High or Medium independent-review findings.
  - Record the behavior change in the Unreleased changelog without claiming that the repository can control or detect every host-specific sandbox implementation.
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/111-bind-provider-auth-to-call-context.md
replan_contract: docs/plan/replanned/contracts/111-bind-provider-auth-to-call-context.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/137-define-noncircular-provider-auth-preflight.md
  - docs/plan/active/138-integrate-provider-auth-call-context.md
inherited_acceptance_digests:
  - sha256:85e7bfc337d9eb3df7ad6f7855a398f0c1dfc726713ea81def14155f3e950ec6
  - sha256:92274d5b0d920f44cf3160b8575bf67a1e9fe78cc416f1ce4b63a95b1f986cae
  - sha256:1953e5545dc5ae4849b19f7ff72dd764dc86238dcca6f83f3ddd7a514357709a
  - sha256:5c3f62412d5f8f8ba69db2978e23f4e5e1b9e9977e8d9970f3727fc532692965
  - sha256:9e2ec05ab2411d157aa3c1932a02505c0e9a6e941ae342e6d13a6ac061fc1a86
  - sha256:f3338d44f65d610e427e266ecd7546885cd4ecab888667d318915c68ed21d2ec
  - sha256:fb13b9dfdc131cb22004dbc3d0a80836df018f5bb365d585297bd5b9ba46856b
  - sha256:1fecb125600a276fc33797d62c037699546e779c113361e0639e97509db827dd
  - sha256:2d6dd62fff567e26a63854fca58a084beb770d4267cb275c0d29c0e549cfd7b6
  - sha256:60534aab834531b34831a12df1f57b2e6701dd3770b755d50a63aa589edf9337
  - sha256:50aa4e3f7c377552b933a1ff2630f290fd20a396c93d1a745f0f5b4e3e024aeb
  - sha256:746fc1d291a0e57ec8e3e4cc8c8ed36f42f4da1a52141946d14700d1f9c9d0fb
  - sha256:8abe73aa0c3163e4f40cb22f62016e11e644dc6bd63196fc209003cee46621ce
  - sha256:972a6b0028d41af2ba50e5980dfc2018bc86a0a201ae0d9036a487a7b46c9b6d
  - sha256:5c4f20a1e7aa748bc0b1fafc34eea2bbabb52c612946bcaff51b8f7d17c96651
checked_summary_ja: 外部providerの認証確認を実際の呼び出し環境へ結合し、sandbox内外とprovider間で認証事実を誤用しないようにする。

## Context

The provider-call execution context is the provider, command execution boundary, and credential source used for one exact external-provider call.

A non-mutating provider and identity check executed through the same provider and command boundary intended for the later external call.

The sandboxed GitHub CLI process reported invalid credentials from `hosts.yml`, while the approved host process used the OS keyring and authenticated the same active account.

The observed failure of the sandboxed gh process to obtain a valid credential while another approved process environment obtained the OS keyring credential.

This process-specific failure does not establish that the user account is logged out.

The GitHub App reached the provider but lacked repository collaborator permission, and the browser fallback had no configured backend.

The GitHub API rejection stating that the connected account must be a repository collaborator before creating the pull request.

This rejection is a provider permission failure, not credential-source evidence for another provider.

These outcomes establish separate credential-access, provider-permission, and provider-availability boundaries that the current generic workflow does not state precisely enough.

Host approval to run a command outside a sandbox and project authorization for the exact provider operation, target, and effect.

These are independent conditions.

Authentication preflight and diagnostics that report only provider availability, account identity when available, credential source class, and sanitized errors without token values.

## Decisions

- Use the provider-call execution context to scope runtime configuration and authentication evidence for one exact external call.
- Clarify the existing `runtime_configured` semantics without changing either external-service policy schema.
- Keep host-specific escalation syntax and credential-store implementation out of reusable templates.
- Add one direct `mcp-ops` reference for detailed execution-context and failure-routing guidance while keeping the skill body concise.
- Treat host sandbox approval and exact external target-and-effect authorization as independent gates.
- Distinguish credential-source unavailability, authenticated provider permission denial, and unavailable backend outcomes before selecting a fallback.
- Use sanitized synthetic scenarios for deterministic validation and keep live credentials and external writes outside tests.

## Tasks

- [ ] Update root and generated external-service specifications with provider-call execution-context semantics and unchanged schema guarantees.
- [ ] Update root and generated `mcp-ops` skills, direct references, and UI metadata without changing the discovery bridge trigger.
- [ ] Extend managed inventories, normalized parity checks, and generated-project assertions for the new reference.
- [ ] Add fixed scenario fixtures and deterministic condition-to-action validation for authentication, permission, fallback, duplicate prevention, and credential-denial cases.
- [ ] Verify supported Copier copy and update paths preserve project-owned policy and product files without conflicts, rejection files, or unclassified deletion.
- [ ] Run focused validation, independent security and semantic review, the authoritative validation suite, and archive the accepted plan.

## Validation Notes

- Decision audit selected provider-generic execution-context semantics, no policy-schema migration, one direct Skill reference, and synthetic deterministic scenarios.
- The advisory referent contract sealed the provider-call execution context separately from credential-source unavailability, provider permission denial, host sandbox approval, and external-write authorization.
