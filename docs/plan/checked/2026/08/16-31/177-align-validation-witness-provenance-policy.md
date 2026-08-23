# Align validation-witness migration provenance policy

status: checked
primary_invariant: root and generated policy describe one identical guardian, snapshot, attempt-state, recovery, and threat boundary
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - AGENTS.md
  - references/orchestration.md
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/181-verify-plan176-successor-acceptance.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
replan_source: docs/plan/active/163-capture-validation-witness-migration-provenance.md
replan_contract: docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
integration_gates:
  - Plans 180 and 181 must be checked and their exact checked archive paths must replace the active context paths before implementation
  - generated policy must preserve the same concrete lifecycle and must not broaden the guardian security guarantee
  - Plan 178 must not start until this plan is checked and its exact checked archive path replaces this active dependency
successor_plans:
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: guardian、snapshot、attempt state、復旧条件、脅威境界をrootと生成先の方針で一致させる。

## Decisions

- Use only the controlled terms accepted by Plan 180 and define each term at its first normative use.
- Require the before-stage guardian to remain live through the matching after-stage request; a durable snapshot or Git-local attempt state alone never authorizes compatibility.
- Document prepared, pending, consumed, same-live-attempt resume, and verified pre-boundary stale recovery without introducing a second lifecycle.
- Preserve non-destructive Copier ownership: the migration snapshot is compatibility evidence, not product acceptance evidence, and no update may overwrite unrelated project-owned state.
- Keep root and generated prose semantically aligned and explicitly bound the guarantee to replay without the original guardian.

## Tasks

- [x] Review the preserved policy candidate against the accepted Plan 180 protocol and Plan 181 successor acceptance, and remove static-receipt claims.
- [x] Align root AGENTS and orchestration reference with generated AGENTS and SPEC_ORCHESTRATION.
- [x] Extend the root policy checker with deterministic markers for capability commitment, challenge-response, lifecycle, recovery, one-hour timeout, and threat boundary.
- [x] Run focused validation and independent read-only review; archive and commit only after zero unresolved High or Medium findings.

## Validation Notes

- This plan changes prose and policy markers only; checked Plan 180 is the executable protocol authority and checked Plan 181 is the dependency gate.
- Parent-direct execution ledger `/tmp/plan177-execution-state.json` records the reviewed Plan 177 diff, one focused validation event, and one authoritative validation event.
- Independent review round 1 reported High 0, Medium 2, and Low 0 for expiry recovery and socket-identity overclaims. Bounded remediation aligned the prose with partial-publication recovery and capability-based guardian proof.
- Independent review round 2 reported Accept with High 0, Medium 0, and Low 0.
- Focused and authoritative validation each passed `python3 scripts/check-root-agent-policy.py`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
- Repository completion validation passed `scripts/lint-project-workflow.sh` and `tests/smoke.sh`; actionlint was unavailable and the repository scripts reported its configured skip.
