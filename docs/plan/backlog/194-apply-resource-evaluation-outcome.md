# Apply the resource-bounded orchestration evaluation outcome

status: backlog
primary_invariant: the documented default changes only for a checker-validated measured pass and otherwise remains unchanged with an explicit bounded outcome
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
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/resource-evaluation-decision-v1.json
  - tests/smoke.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
  - scripts/check-root-agent-policy.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require zero unresolved High or Medium independent-review findings, no safety-gate regression, at least 30 percent lower median model starts and median time to accepted patch than the paired baseline, and p95 time to accepted patch no more than 10 percent worse than the paired baseline.
  - Reject a measured pass when either side uses different requirements, source state, validation authority, correction budget, model availability treatment, external access, credentials, or manual intervention not represented in the paired evidence.
  - Keep the current path as the default and record `measurement_pending` or `measured_fail` when evidence is unavailable, incomplete, noncomparable, or below any threshold; do not claim improvement from historical unpaired runs.
  - Promote the staged path to the documented default only after the checker validates every evidence digest and threshold; preserve an explicit, tested rollback to the prior default without deleting evidence or rewriting prior outcomes.
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:74676af1c3fd1ec6c706498604bbe8b3f2cbbcb4dd8a1ffaf172718f73726583","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:1573727361ca97cecd78c1402e5da1408485636d354b073d41538c0e6f7f1293","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:93709976edad8b54f41e89a815beb179fcdf85a17ac3a8a7205d89d7e6d91a2a","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:d5e7d033295d031afe5825359b3d986cea2182dccb3cafbed36972cfff29c735","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py --include-holdout"}
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
replan_source: docs/plan/active/133-evaluate-resource-bounded-orchestration.md
replan_contract: docs/plan/replanned/contracts/133-evaluate-resource-bounded-orchestration.json
predecessor_plans:
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
integration_gates:
  - Plan 193 must be checked and its exact checked archive path must replace this active predecessor before interpreting the outcome
  - in the same parent-owned activation update, add the baseline, staged, and result records emitted by checked Plan 193 as exact read-only context
  - change the default only for a checker-validated measured pass; preserve the current default for measurement_pending, measured_fail, or any safety or comparability rejection
  - Plan 195 remains deferred until this plan is checked and its exact checked archive path replaces its active predecessor
successor_plans:
  - docs/plan/active/192-freeze-resource-evaluation-contract.md
  - docs/plan/active/193-collect-resource-evaluation-evidence.md
  - docs/plan/active/194-apply-resource-evaluation-outcome.md
  - docs/plan/active/195-verify-plan133-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:74676af1c3fd1ec6c706498604bbe8b3f2cbbcb4dd8a1ffaf172718f73726583
  - sha256:1573727361ca97cecd78c1402e5da1408485636d354b073d41538c0e6f7f1293
  - sha256:93709976edad8b54f41e89a815beb179fcdf85a17ac3a8a7205d89d7e6d91a2a
  - sha256:d5e7d033295d031afe5825359b3d986cea2182dccb3cafbed36972cfff29c735
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 検証済みの測定結果が全条件を満たす場合だけ既定経路を変更し、それ以外は現状を維持する。

## Decisions

- Apply the accepted median, p95, quality, safety, comparability, and directly observed token thresholds exactly.
- Apply the frozen default-selection and rollback checks without editing the checker or any Plan 193 evidence, and record the interpretation separately in resource-evaluation-decision-v1.json.
- Align root and generated policy, Skill, checker, smoke, Copier preservation, and the Unreleased record without overstating causality.
- Do not run the complete source authoritative suite; Plan 195 retains that one combined run.
- Use bounded parent implementation and independent review because this slice changes validation authority and default policy.

## Tasks

- [ ] Verify the checked Plan 193 outcome against every threshold and rejection condition.
- [ ] Record the bounded decision artifact and either preserve the current default or apply the staged default with rollback without modifying the measured result.
- [ ] Align the exact root and generated paths and add deterministic default and rollback checks.
- [ ] Complete focused validation and independent review, archive, commit, and activate Plan 195.

## Validation Notes

- A non-pass outcome is a valid completion and must not be rewritten as an improvement.
