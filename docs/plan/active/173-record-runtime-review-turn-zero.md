# Record runtime review turn zero

status: in_progress
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: review inheritance is observed only when runtime-produced transcript or hook evidence binds the reviewer session and bounded packet to inherited turn count zero
write_scope:
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - scripts/agent-log-event.py
  - scripts/check-agent-log-manifest.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/import-codex-transcript.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/docs/agent/SPEC_AGENT_LOGGING.md
  - template/.project-agent-workflow/docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - template/.project-agent-workflow/hooks/agent_log_event.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - template/.project-agent-workflow/scripts/check-agent-log-manifest.py
  - template/.project-agent-workflow/scripts/import-codex-transcript.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/hooks/logging.py
  - tests/test-plan-execution-state.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/168-verify-runtime-session-resource-evidence.md
  - docs/plan/checked/2026/08/16-31/169-linearize-session-checkpoint-lifecycle.md
  - docs/plan/replanned/2026/08/16-31/132-checkpoint-plan-session-resources.md
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 -m pytest tests/hooks
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 -m pytest tests/hooks
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Give an independent reviewer only the unchanged plan, admitted diff, bounded receipts, and applicable specifications after the candidate is otherwise review-ready; permit one initial review and one bounded rereview per candidate before the existing strategy-change path, and do not reuse an accumulated general-purpose reviewer history across numbered plans.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc","stage":"focused","witness":"python3 -m pytest tests/hooks"}
replan_source: docs/plan/active/170-bind-review-context-to-candidate-lifecycle.md
replan_contract: docs/plan/replanned/contracts/170-bind-review-context-to-candidate-lifecycle.json
integration_gates:
  - Plan 172 must be checked and its exact archive must replace the active context path
  - Unavailable runtime turn evidence remains not_observed rather than inferred
  - Plan 175 revalidates the complete source acceptance
successor_plans:
  - docs/plan/active/172-bind-review-to-candidate-leaf.md
  - docs/plan/active/173-record-runtime-review-turn-zero.md
  - docs/plan/active/174-linearize-reviewer-session-registry.md
  - docs/plan/active/175-integrate-candidate-review-boundaries.md
inherited_acceptance_digests:
  - sha256:86bc3a11238d614d9f4c64f46e1d43b192886250498623253acd5d3cf652eacc
checked_summary_ja: review packetが継承turn 0で渡された事実をruntime証拠だけから確定する。

## Decisions

- review-turn-zero-observation means runtime-produced evidence that binds one reviewer session and review packet to inherited turn count zero.
- Do not infer turn zero from SessionStart, a fresh orchestration id, elapsed time, compaction, or caller-provided counters.
- When the runtime omits an explicit packet turn observation, preserve not_observed and stop only the staged review path.

## Tasks

- [ ] Extend transcript and hook observation schemas with an explicit bounded review-packet turn observation.
- [ ] Verify source bytes and evidence digests before marking reviewer inheritance observed.
- [ ] Bind the observation to the candidate review leaf and receipt packet digest.
- [ ] Add rejection tests for SessionStart-only, caller-fabricated, mismatched packet, and changed evidence.
- [ ] Align root and generated logging policy and validation.
- [ ] Run focused validation, independent review, authoritative validation once, archive, and commit.

## Validation Notes

- Plan 170 was restructured after its bounded rereview found unresolved candidate identity, runtime evidence, and reviewer-history boundaries.
