# Define non-circular provider authentication evidence

status: replanned
task_types:
  - external_services
  - security
  - skill_authoring
  - referent_first
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
replan_reason_codes:
  - parent_remediation_budget_exhausted
write_scope:
  - .codex/skills/mcp-ops/SKILL.md
  - .codex/skills/mcp-ops/agents/openai.yaml
  - .codex/skills/mcp-ops/references/provider-call-execution-context.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - template/.project-agent-workflow/skills/mcp-ops/SKILL.md
  - template/.project-agent-workflow/skills/mcp-ops/agents/openai.yaml
  - template/.project-agent-workflow/skills/mcp-ops/references/provider-call-execution-context.md
  - tests/fixtures/mcp-ops/scenarios.json
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
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
  - git diff --check
acceptance:
  - Define the provider-call execution context as the provider, command execution boundary, and credential source used for one exact external call.
  - Treat `runtime_configured` as satisfied only by configuration and authentication evidence obtained for the provider-call execution context that will perform the exact call; changing the provider, account, credential source, or command boundary invalidates that evidence and requires a new preflight and fresh authorization check.
  - Keep host approval to execute outside a sandbox separate from project authorization for the exact provider operation, target, and effect; require both when both apply, and never treat a saved command-prefix approval as external-write authorization.
  - When a minimal non-mutating authentication check fails only in the current sandbox while the user reports a valid login elsewhere, allow one approved check through the intended provider-call execution context before requesting reauthentication; if that check remains unavailable or inconclusive, fail closed and report the exact missing capability.
  - Distinguish inability to obtain credentials in one process environment, rejection of an authenticated account's provider permission, and absence of a configured backend; do not collapse these conditions into a generic login failure.
  - Do not reuse connector authentication evidence for GitHub CLI calls, GitHub CLI evidence for connectors, or browser session evidence for either; switching provider requires its own provider check and a fresh external-service authorization for the exact target and effect.
  - Keep retries non-mutating until the provider-call execution context is selected, prevent duplicate external writes with an exact remote-state read when the operation supports one, and never retry a protected write through another provider without current-task authorization and any required exact confirmation.
  - Permit diagnostics to report only sanitized provider availability, account identity when the provider exposes it safely, credential-source class, execution-boundary class, and error classification; never read, print, persist, or place token values or credential material in fixtures, policy, logs, or provider payloads.
  - Keep `mcp-ops` `SKILL.md` concise, place detailed execution-context and failure-routing guidance in one directly linked reference, and keep root and generated `SKILL.md`, reference, and `agents/openai.yaml` semantics aligned after path normalization.
  - Add structured median, edge, negative, and untuned holdout scenarios covering same-context success, sandbox-local credential lookup failure with approved host-context success, authenticated provider permission denial, provider or command-boundary change after preflight, unavailable fallback, duplicate-write prevention, and attempted credential persistence.
  - Validate every structured scenario's exact conditions and expected next action deterministically; keep live keyring access, live connector access, browser sessions, and external writes outside deterministic tests.
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/137-define-noncircular-provider-auth-preflight.md
replan_contract: docs/plan/replanned/contracts/137-define-noncircular-provider-auth-preflight.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/139-reject-blank-provider-context-bindings.md
  - docs/plan/active/140-integrate-concrete-provider-context-bindings.md
inherited_acceptance_digests:
  - sha256:85e7bfc337d9eb3df7ad6f7855a398f0c1dfc726713ea81def14155f3e950ec6
  - sha256:92274d5b0d920f44cf3160b8575bf67a1e9fe78cc416f1ce4b63a95b1f986cae
  - sha256:5c3f62412d5f8f8ba69db2978e23f4e5e1b9e9977e8d9970f3727fc532692965
  - sha256:9e2ec05ab2411d157aa3c1932a02505c0e9a6e941ae342e6d13a6ac061fc1a86
  - sha256:f3338d44f65d610e427e266ecd7546885cd4ecab888667d318915c68ed21d2ec
  - sha256:fb13b9dfdc131cb22004dbc3d0a80836df018f5bb365d585297bd5b9ba46856b
  - sha256:1fecb125600a276fc33797d62c037699546e779c113361e0639e97509db827dd
  - sha256:2d6dd62fff567e26a63854fca58a084beb770d4267cb275c0d29c0e549cfd7b6
  - sha256:60534aab834531b34831a12df1f57b2e6701dd3770b755d50a63aa589edf9337
  - sha256:746fc1d291a0e57ec8e3e4cc8c8ed36f42f4da1a52141946d14700d1f9c9d0fb
  - sha256:8abe73aa0c3163e4f40cb22f62016e11e644dc6bd63196fc209003cee46621ce
checked_summary_ja: 認証済みという前提を置かずに一回の非変更 identity read を許可し、その結果だけを同一実行文脈の認証根拠として扱う。

## Decisions

- Keep the external-service policy schemas unchanged and express the one identity read as a bounded procedural prerequisite.
- Require current-task relevance, exact provider, operation, target, payload, and ordinary effect as project authorization for that read; require host execution approval as a separate gate when the selected command boundary needs it.
- Do not run the ordinary `runtime_configured` authorization command for the read that establishes authentication.
- After a successful read, run a fresh ordinary authorization for the intended call's exact tuple and complete effects.

## Referent Contract

- One local non-provider check of the exact selected credential source in the selected command execution boundary, with only its credential-source class available to diagnostics.
- A project-authorization decision over the identity read provider, operation, target, payload, ordinary effect, and current-task relevance, excluding host execution approval and any authenticated-result assertion.
- A host execution approval for the selected command boundary when that boundary requires approval, excluding authorization for any provider operation, target, payload, or effect.
- One exact non-mutating provider identity read executed only after its project authorization and any separately required host execution approval pass.
- Process-local or otherwise ephemeral authentication evidence bound to provider, account, command execution boundary, and exact selected credential source, while diagnostics expose only the credential-source class.
- A fresh decision over the intended call provider, operation, target, payload, complete effect set, current-task relevance, scoped authentication evidence, and exact confirmation when required.
- One provider call whose provider, operation, target, payload, effects, account, command boundary, and exact credential source match the accepted evidence and authorization facts.

## Tasks

- [ ] Correct the root and generated policy, Skill, reference, and UI metadata.
- [ ] Correct structured scenarios and deterministic mappings, including unauthorized identity-read and context-change failures.
- [ ] Run focused checks and independent security and semantic review.

## Validation Notes

- Plan 111 stopped after two parent-direct review rounds exposed a circular prerequisite. Its dirty semantic and fixture paths are preserved in this successor scope.
