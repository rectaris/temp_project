# Advanced Validation Lifecycle

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `scripts/`
  - `template/scripts/`
  - `template/docs/agent/SPEC_VALIDATION.md.jinja`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja`
  - `template/docs/agent/SPEC_FILE_MANAGEMENT.md`
  - `scripts/check-copier-template.py`
  - `tests/smoke.sh`
  - `docs/plan/plan.md`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `tests/copier-update.sh`
  - `python3 scripts/validate-changes.py`
  - `python3 scripts/plan_validation_commands.py --self-test`
  - `python3 scripts/check-codex-toml.py`
  - `git diff --check`
- `acceptance`:
  - Root and generated projects include generic validation command allowlist tooling.
  - Root and generated projects include a Codex TOML parser check.
  - Generated `validate-changes.py` remains project-agnostic and routes checks from generic file patterns.
  - Generated docs describe advanced Linear lifecycle boundaries without enabling external writes.
  - Template checks and smoke tests require the new generic scripts.
- `acceptance_focus`:
  - safe validation command parsing
  - generic change-aware validation
  - external-write disabled-by-default lifecycle policy
- `expected_output`: root and template validation lifecycle scripts, generated docs and tests, checked plan record.
- `checked_summary_ja`: supportcard-status 由来の検証コマンド allowlist、Codex TOML 検査、change-aware validation、Linear lifecycle 境界を汎用化して root とテンプレートへ追加した。
- `completion_deferred_reason`: ``

## Goal

Genericize supportcard-status validation and lifecycle operations that are not project-domain-specific, then apply them to both this template repository root and generated projects.

## Decisions

1. Do not port supportcard-status domain checks such as schedule contracts, delegation audits, runtime JSON contracts, or game-specific data reconstruction.

2. Use a compact built-in validation profile instead of a full YAML policy parser for this pass; generated projects can extend `validate-changes.py` locally.

3. Keep Linear lifecycle support documented as an advanced external-service boundary. Do not generate a write-capable Linear sync implementation until a generated project configures `linear_sync` beyond `documented`.

4. Keep backup-file preservation in `SPEC_FILE_MANAGEMENT.md`; it is already generic and generated.

## Tasks

- [x] Add root and template `scripts/plan_validation_commands.py`.
- [x] Add root and template `scripts/check-codex-toml.py`.
- [x] Upgrade template `scripts/validate-changes.py` and add root counterpart.
- [x] Add root and template generic `scripts/sync-plan-to-linear.sh`.
- [x] Update generated validation, plan workflow, and external-service docs.
- [x] Update template required-file checks.
- [x] Update smoke tests.
- [x] Run validation commands.
- [x] Archive this plan after validation.

## Validation Notes

Validated with:

- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `tests/copier-update.sh`
- `python3 scripts/validate-changes.py`
- `python3 scripts/plan_validation_commands.py --self-test`
- `python3 scripts/check-codex-toml.py`
- `git diff --check`

`tests/smoke.sh` and `tests/copier-update.sh` emitted Copier `DirtyLocalWarning` because they rendered or updated from uncommitted local template changes, then passed.
