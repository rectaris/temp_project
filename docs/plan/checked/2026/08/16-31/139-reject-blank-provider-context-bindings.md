# Reject blank provider-call context bindings

status: checked
task_types:
  - external_services
  - security
  - referent_first
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
primary_invariant: a successful identity-read evaluation requires non-empty concrete provider-call context bindings, not merely equal values
write_scope:
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/fixtures/mcp-ops/scenarios.json
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/138-integrate-provider-auth-call-context.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Define the provider-call execution context as the provider, command execution boundary, and credential source used for one exact external call.
  - Treat `runtime_configured` as satisfied only by configuration and authentication evidence obtained for the provider-call execution context that will perform the exact call; changing the provider, account, credential source, or command boundary invalidates that evidence and requires a new preflight and fresh authorization check.
  - Do not reuse connector authentication evidence for GitHub CLI calls, GitHub CLI evidence for connectors, or browser session evidence for either; switching provider requires its own provider check and a fresh external-service authorization for the exact target and effect.
  - Permit diagnostics to report only sanitized provider availability, account identity when the provider exposes it safely, credential-source class, execution-boundary class, and error classification; never read, print, persist, or place token values or credential material in fixtures, policy, logs, or provider payloads.
  - Add structured median, edge, negative, and untuned holdout scenarios covering same-context success, sandbox-local credential lookup failure with approved host-context success, authenticated provider permission denial, provider or command-boundary change after preflight, unavailable fallback, duplicate-write prevention, and attempted credential persistence.
  - Validate every structured scenario's exact conditions and expected next action deterministically; keep live keyring access, live connector access, browser sessions, and external writes outside deterministic tests.
replan_source: docs/plan/active/137-define-noncircular-provider-auth-preflight.md
replan_contract: docs/plan/replanned/contracts/137-define-noncircular-provider-auth-preflight.json
integration_gates:
  - matching empty strings must produce a deterministic fail-closed action
  - plan 140 must revalidate every Plan 137 acceptance item before Plan 138 resumes
successor_plans:
  - docs/plan/active/139-reject-blank-provider-context-bindings.md
  - docs/plan/active/140-integrate-concrete-provider-context-bindings.md
inherited_acceptance_digests:
  - sha256:85e7bfc337d9eb3df7ad6f7855a398f0c1dfc726713ea81def14155f3e950ec6
  - sha256:92274d5b0d920f44cf3160b8575bf67a1e9fe78cc416f1ce4b63a95b1f986cae
  - sha256:fb13b9dfdc131cb22004dbc3d0a80836df018f5bb365d585297bd5b9ba46856b
  - sha256:2d6dd62fff567e26a63854fca58a084beb770d4267cb275c0d29c0e549cfd7b6
  - sha256:746fc1d291a0e57ec8e3e4cc8c8ed36f42f4da1a52141946d14700d1f9c9d0fb
  - sha256:8abe73aa0c3163e4f40cb22f62016e11e644dc6bd63196fc209003cee46621ce
checked_summary_ja: provider-call context の必須値が空のまま一致するケースを拒否し、具体的な実行文脈だけを認証根拠へ結合する。

## Decisions

- Validate each provider, account, command-boundary, exact credential-source, and diagnostic class value as a non-empty string before comparing contexts.
- Return a fail-closed action before fresh intended-call authorization when any required binding is blank.
- Add deterministic mutations of the median scenario that prove blank bindings are rejected.

## Referent Contract

- Non-empty provider, account, command-boundary, and exact credential-source values bound to one successful provider identity read and the intended call authorization request.
- One non-empty credential-source class derived from the exact selected source and exposed only in sanitized diagnostics.
- A deterministic fail-closed next action produced when provider, account, command boundary, exact credential source, or credential-source class is absent or blank.

## Tasks

- [x] Reject blank context bindings in the condition-driven evaluator.
- [x] Add deterministic blank-binding regression coverage without weakening existing scenario mappings.
- [x] Run focused validation and independent review.

## Validation Notes

- Plan 137 stopped after two parent-direct review rounds; the preserved checker and fixture diff remains unaccepted.
- Implemented nonblank validation for selected source, account, evidence and intended provider, command boundary, exact source, and diagnostic source class.
- Ten isolated blank-binding mutations fail before fresh intended-call authorization.
- Focused and authoritative validation each passed `check-root-agent-policy.py`, `check-copier-template.py`, and `git diff --check`.
- Independent review reported High 0, Medium 0, Low 0; Plan 140 remains responsible for the full Plan 137 semantic integration and Plan 138 resume gate.
