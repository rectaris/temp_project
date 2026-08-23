# Admit live validation-witness guardian implementation

status: checked
primary_invariant: a post-update compatibility decision is authorized only by the same bounded live process that observed the exact clean committed source before the update
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
  - scripts/snapshot-validation-witness-provenance.py
  - tests/test-copier-migration.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/08/16-31/176-establish-live-validation-witness-provenance.md
  - template/.project-agent-workflow/scripts/validate-copier-update.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - pytest tests/test-copier-migration.py
  - git diff --check
validation:
  - pytest tests/test-copier-migration.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"pytest tests/test-copier-migration.py"}
replan_source: docs/plan/active/176-establish-live-validation-witness-provenance.md
replan_contract: docs/plan/replanned/contracts/176-establish-live-validation-witness-provenance.json
integration_gates:
  - initialize a fresh parent-owned execution ledger and treat all Plan 176 review and validation evidence as advisory history only
  - Plan 181 must not start until this plan is checked and its exact checked archive path replaces the active dependency
successor_plans:
  - docs/plan/active/180-admit-live-validation-witness-guardian.md
  - docs/plan/active/181-verify-plan176-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 保存済みguardian実装を新しい実行台帳、独立レビュー、focused検証で受け入れる。

## Decisions

- live-provenance guardian implementation means the preserved snapshot script and deterministic migration tests admitted only through this fresh successor run.
- Preserve every accepted guardian, capability, challenge-response, state-transition, recovery, confinement, byte-limit, expiry, and threat-boundary decision from replanned Plan 176.
- Reuse the dirty script and test only as unaccepted candidate input; prior reviews and tests do not satisfy this plan's acceptance gates.
- Use bounded parent implementation because the plan retains a high-risk local security boundary, and require a fresh independent read-only review before validation.
- Stage and commit only the two declared implementation paths plus parent-owned plan lifecycle files.

## Tasks

- [x] Recheck the preserved candidate against the replanned source decisions and initialize a fresh execution ledger bound to this plan and current source baseline.
- [x] Obtain a fresh independent review and apply only bounded in-scope corrections until zero unresolved High or Medium findings remain or this new run reaches a mandatory stop.
- [x] Run the focused validation and the authoritative validation sequence exactly once under the new run.
- [x] Archive and commit only after the implementation diff, review receipts, validation witnesses, and plan lifecycle all satisfy the successor gates.

## Validation Notes

- Plan 176's final rereview reported zero unresolved High or Medium findings, but that evidence remains advisory because its execution ledger is terminal.
- Fresh ledger `/tmp/plan180-execution-state.json` is bound to source HEAD `01e3217fe529d175713f29b208c4692e3b8e73b9` and records one focused and one authoritative validation event.
- Independent review round 1 reported High 0, Medium 3, and Low 1. One bounded remediation added consumed-state replay and partial-publication coverage, negative stale-recovery cases, the exact threat boundary, and lifetime-boundary tests.
- Bounded rereview `.agent-artifacts/reviews/180-guardian-review-round-2.md` reported Accept with High 0, Medium 0, and Low 0.
- Focused and authoritative validation each passed all 31 `pytest tests/test-copier-migration.py` cases plus `git diff --check`. The socket/process tests required execution outside the restricted syscall sandbox; the sandbox-only `EPERM` result was not recorded as a product validation event.
- This plan does not edit policy, Copier wiring, source inventory, smoke coverage, or the change log.
