# Verify runtime session resource evidence

status: checked
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: only runtime-produced transcript or hook evidence may mark root-session identity or reviewer inheritance as observed
write_scope:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - scripts/agent-log-event.py
  - scripts/check-agent-log-manifest.py
  - scripts/import-codex-transcript.py
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - tests/hooks/logging.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
required_specs:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 -m pytest tests/hooks
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 -m pytest tests/hooks
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Record provider-observed input, cached input, output, reasoning, model-response, compaction, helper-turn, and tool-call measurements only when directly available, keep unavailable values as not_observed, store no prompts or output bodies, and use deterministic proxy counts without estimating tokens.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7","stage":"focused","witness":"python3 -m pytest tests/hooks"}
replan_source: docs/plan/active/132-checkpoint-plan-session-resources.md
replan_contract: docs/plan/replanned/contracts/132-checkpoint-plan-session-resources.json
integration_gates:
  - verify identity and inheritance only from bounded runtime-produced evidence whose source digest is bound to the stored transcript or hook log
  - Plan 169 must start in a different directly observed root session after this plan is checked
successor_plans:
  - docs/plan/active/168-verify-runtime-session-resource-evidence.md
  - docs/plan/active/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
  - docs/plan/active/171-integrate-session-resource-boundaries.md
inherited_acceptance_digests:
  - sha256:cf0c0eaf1b20d2e1a87a62c8c9b82f72b208c16e7ed984058ce9f596df8d15a7
checked_summary_ja: runtimeが生成した証拠だけからsession identityと利用量の観測状態を確定する。

## Decisions

- Accept observed root-session identity and reviewer inheritance only from a bounded runtime evidence artifact whose digest is recomputed by the verifier.
- Keep provider token fields separate from deterministic proxy counters.
- Preserve `not_observed` when the runtime omits identity, inheritance, or provider usage.
- Keep prompt, response, reasoning, command, and environment bodies outside manifests and receipts.

## Tasks

- [x] Define the runtime evidence schema and source-digest binding.
- [x] Verify transcript and hook provenance before marking identity or inheritance observed.
- [x] Preserve no-overwrite transcript and manifest correspondence.
- [x] Add deterministic rejection tests for caller-fabricated observations and mismatched evidence.
- [x] Run focused validation, independent review, authoritative validation once, archive, and commit.

## Validation Notes

- Plan 132 rereview rejected caller-created manifest and inheritance claims as insufficient evidence.
