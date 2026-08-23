# Establish live validation-witness migration provenance

status: in_progress
primary_invariant: a post-update compatibility decision is authorized only by the same bounded live process that observed the exact clean committed source before the update
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
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
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
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
replan_source: docs/plan/active/163-capture-validation-witness-migration-provenance.md
replan_contract: docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
integration_gates:
  - the validation-witness-migration-guardian must be listening before the durable snapshot and pending attempt state become authoritative
  - Plan 177 must not start until this plan is checked and its exact checked archive path replaces this active dependency
successor_plans:
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/178-wire-validation-witness-copier-transition.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 更新前の同一live processだけが旧形式witnessの更新後検証を許可できる状態遷移を実装する。

## Decisions

- validation-witness-migration-guardian means the bounded local process started from the clean pre-update project that alone may authorize the matching after-stage transition.
- validation-witness-migration-snapshot means the bounded canonical record of exact committed pre-schema integration-plan evidence for one source commit.
- validation-witness-migration-attempt-state means the prepared, pending, or consumed Git-metadata state for one source commit, snapshot digest, and live guardian identity.
- validation-witness-migration-integration-gate means the condition that every migration slice and the real versioned transition pass without unresolved High or Medium review findings.
- Start the guardian only after fixing a clean HEAD and validating exact plan, acceptance, validation, contract, and archive identities. Use a private Unix-domain listener under Git metadata and a one-hour production lifetime; tests may request a shorter bounded lifetime.
- Generate a 32-byte random capability inside the guardian and never write it to disk, environment, command arguments, or logs. Bind its SHA-256 commitment to the protocol version, attempt identifier, source HEAD, snapshot digest, and fixed domain separator in prepared and pending state; neither socket pathname nor PID is identity evidence.
- Require after-stage challenge-response: the client sends a fresh 32-byte challenge and exact attempt-state digest, the guardian returns a capability-bound response, the client verifies the durable commitment and returns a capability-bound consume acknowledgement, and only then may the guardian revalidate and durably consume the exact attempt.
- Publish prepared state before the worktree snapshot, promote it to pending only after the guardian is ready and exact snapshot bytes are durable, and let only the authenticated guardian perform the effect-adjacent pending-to-consumed transition.
- Resume an attempt only while its original capability-holding guardian is live. After a durable consume and lost response, that same live guardian may revalidate the exact consumed tuple and return idempotent success; a dead-guardian or copied consumed state always fails as replay.
- Permit explicit stale-attempt recovery only when the guardian is dead, the clean source HEAD and pre-boundary policy are unchanged, the exact prepared or pending artifacts match, and the target boundary is absent. A consumed state is never removed by recovery.
- Constrain worktree paths to normalized repository-relative paths and Git metadata and socket paths to normalized relative paths beneath the canonical Git directory. For every applicable input, reject absolute paths, traversal, dot segments, backslashes, NUL, out-of-root resolution, final symlinks, and symlink ancestors; reject socket bind or peer-credential checks that cannot establish the required confinement.
- Fix the limits at 4,096 UTF-8 bytes per normalized path, 256 KiB per plan or archive, 1 MiB per contract, 256 KiB per policy, 64 KiB for Copier answers, 512 KiB for the snapshot, 16 KiB for attempt state, 16 KiB per protocol message, 64 captured plans, and a 32-byte challenge and capability. Read at most each limit plus one byte and reject overflow before parsing.
- Treat consumed as terminal for the version boundary except for the same-live-guardian idempotent response rule. Reject missing, dirty, stale, unsafe-path, cross-clone, expired, post-boundary, mismatched, and replayed evidence.
- State the security boundary exactly: copying repository and Git-local files without the original live guardian fails; an unrestricted same-user actor that can replace every local process and file is outside this guarantee.

## Tasks

- [ ] Replace the static receipt candidate with the capability-holding guardian, canonical snapshot, and prepared/pending/consumed attempt-state protocol.
- [ ] Make every interrupted publication and consume point deterministically resumable or recoverable without accepting partial state.
- [ ] Add deterministic tests for genuine use, challenge-response mismatch, socket and PID replacement, same-live-guardian response-loss retry, verified stale recovery, timeout, cross-clone copying, pathname replacement, every partial publication and consume point, dirty or changed HEAD, every rejected path class, every byte boundary, and replay after the guardian dies.
- [ ] Run focused validation and independent read-only review; archive and commit only after zero unresolved High or Medium findings.

## Validation Notes

- Reuse only candidate hunks that satisfy this state machine. The existing static receipt is not acceptance evidence.
- This plan does not edit Copier policy or the authoritative fixture.
- One disposable downstream Git project copied at v1.4.4 and updated to a synthetic v1.4.5 target that includes the snapshot script in the single copy-and-stage inventory. This concrete authoritative transition is delegated to Plan 179.
