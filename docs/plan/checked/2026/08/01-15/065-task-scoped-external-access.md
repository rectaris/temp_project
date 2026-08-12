# Permit task-scoped external access by default

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
  - skill_authoring
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - .codex/skills/
  - copier.yml
  - docs/agent/
  - docs/plan/
  - references/
  - scripts/
  - template/
  - tests/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - .agent-artifacts/referent-contracts/task-scoped-external-access/contract.json
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - A generated project can explicitly select task-scoped default external access while the reusable template retains a restricted default.
  - The selected profile permits task-required external reads and ordinary writes without per-operation allowlists.
  - Credential transfer, secret persistence, and exposing write credentials to untrusted code remain denied.
  - Remote deletion, public communication, financial commitment, production change, access-control change, and unclassified writes require exact current-user confirmation.
  - Connection availability and authentication remain separate from operation authorization, and unavailable services use project-local fallbacks.
  - External-service policy checks authorize representative ordinary operations and reject or require confirmation for protected effects deterministically.
  - Existing project-owned version 1 policies remain byte-for-byte preserved by supported Copier updates, with explicit migration guidance instead of automatic permission expansion.
  - Root and generated external-service Skills remain concise and semantically aligned with the policy and validator.
checked_summary_ja: 現在の依頼に必要な外部読み取りと通常の書き込みを既定で許可し、秘密情報と重大な副作用に限定して拒否または個別確認する外部サービス方針を追加した。

## Context

The current generated policy requires every external read and write operation to be listed before use.

The user accepted a design that removes per-operation allowlists for ordinary task-required work while retaining deterministic boundaries for credentials, protected data, destructive effects, public effects, financial commitments, production changes, access-control changes, and unclassified writes.

## Decisions

- Add an explicit Copier-selected task-scoped default-access profile while retaining the restricted profile as the reusable template default.
- Separate service availability and authentication from authorization of an operation requested by the current user task.
- Permit task-required reads and ordinary writes by default under the selected profile.
- Require exact current-user confirmation for protected or unclassified write effects.
- Deny credential material transfer, secret persistence, and exposing write credentials to untrusted code in every profile.
- Preserve existing project-owned version 1 policy files during Copier update and require explicit project migration to the new schema.

## Tasks

- [x] Seal the external-access referents and controlled terms before editing public template contracts.
- [x] Implement the Copier question and version 2 external-service policy template.
- [x] Update generated specifications, Skills, and validators to enforce task scope and protected-effect boundaries.
- [x] Add deterministic generation, authorization, migration, and update-preservation coverage.
- [x] Reconcile root references and policy with the generated-project contract.
- [x] Run required validation, independent review, and archive the completed plan.

## Validation Notes

- `python3 scripts/check-root-agent-policy.py`: passed through `scripts/lint-project-workflow.sh`.
- `python3 scripts/check-copier-template.py`: passed directly and through `scripts/lint-project-workflow.sh`.
- `python3 scripts/validate-changes.py --all`: passed.
- `scripts/lint-project-workflow.sh`: passed; all included unit and lifecycle suites passed.
- `tests/smoke.sh`: passed; actionlint was unavailable and the suite reported its documented skip.
- `tests/copier-update.sh`: passed.
- `git diff --check`: passed.
- Skill authoring validation passed for the root and generated MCP, Linear, graph-memory, and browser-operation skills.
- Required referent contract reached `semantic_review_passed`; an independent change reviewer returned PASS after the denied-effect precedence correction.
- No unresolved implementation or migration risk remains within the accepted scope.
