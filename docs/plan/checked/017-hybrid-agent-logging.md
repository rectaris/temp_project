# Hybrid Agent Logging

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `AGENTS.md`
  - `docs/agent/SPEC_AGENT_LOGGING.md`
  - `docs/agent/SPEC_CONTEXT_COMPRESSION.md`
  - `template/AGENTS.md.jinja`
  - `template/docs/agent/SPEC_AGENT_LOGGING.md`
  - `template/docs/agent/SPEC_CONTEXT_COMPRESSION.md`
  - `template/.codex/hooks/agent_log_event.py`
  - `.codex/hooks/agent_log_event.py`
  - `scripts/agent-log-event.py`
  - `scripts/check-root-agent-policy.py`
  - `scripts/check-agent-log-manifest.py`
  - `template/scripts/check-agent-log-manifest.py`
  - `scripts/check-copier-template.py`
  - `tests/smoke.sh`
  - `tests/test-hooks.py`
- `related_checked_plans`:
  - `docs/plan/checked/009-agent-logging-context-compression.md`
  - `docs/plan/checked/012-root-self-apply-agent-workflow.md`
  - `docs/plan/checked/013-agent-log-hook.md`
  - `docs/plan/checked/016-root-codex-self-apply.md`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
  - `docs/agent/SPEC_AGENT_LOGGING.md`
  - `docs/agent/SPEC_CONTEXT_COMPRESSION.md`
- `validation`:
  - `python3 scripts/check-agent-log-manifest.py --self-test`
  - `python3 scripts/check-copier-template.py`
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `tests/test-hooks.py`
  - `git diff --check`
- `acceptance`:
  - Agent logging policy distinguishes external transcript logs from repo-local hook event logs.
  - External transcript logs are the primary source for complete user/assistant turn reconstruction when available.
  - Repo-local hook event logs remain best-effort corroborating evidence for lifecycle and tool events.
  - Run manifests can list `transcript_log`, `hook_event_log`, `coverage`, and `missing_sources`.
  - Manifest validation can detect present transcript logs, present hook event logs, and missing-source states.
  - Generated projects and root policy preserve the rule that raw logs stay under `.agent-logs/` and are not committed.
  - Active plans and checked records reference run ids and manifest paths only; they do not store full transcripts.
- `acceptance_focus`:
  - hybrid transcript and event logging
  - manifest coverage accounting
  - explicit missing-source reporting
  - root and generated-template parity
- `expected_output`: updated root and generated logging policy, manifest schema checks, hook manifest updates, smoke/self-test coverage, validation output, and checked plan record.
- `checked_summary_ja`: 外側 transcript を一次記録、repo-local hook event を補助証跡として扱う hybrid logging 方針を追加した。
- `completion_deferred_reason`: ``

## Problem

Plans 009, 012, 013, and 016 established local agent log policy and root hook assets, but current behavior does not guarantee that every user/assistant exchange is recorded in this repository.

Repo-local hooks can record lifecycle event payloads only when the Codex environment executes them.

Hook payloads may not contain complete assistant text or full transcript data.

The repository needs a logging design that keeps the useful repo-local hook evidence while making complete transcript capture an explicit primary source when an outer runtime can provide it.

## Goal

Define and implement hybrid agent logging.

Use external transcript logs as the primary source for full turn reconstruction when available.

Use repo-local hook event logs as best-effort corroborating evidence for session, prompt, tool, compact, and stop events.

Make missing log sources visible in each run manifest instead of silently implying complete coverage.

Keep raw logs local under `.agent-logs/` and keep durable plan records as summaries with run ids and manifest paths.

## Decisions

1. External transcript logs are primary for full user/assistant turn reconstruction.

2. Repo-local hook event logs are corroborating evidence and must remain best-effort.

3. This repository owns the transcript ingestion contract and manifest validator, not a specific external capture runtime.

4. Store transcript records under `.agent-logs/<run-id>/raw/transcript.jsonl` when available.

5. Store hook event records under `.agent-logs/<run-id>/raw/events.jsonl` when hooks run.

6. Extend `manifest.json` with `transcript_log`, `hook_event_log`, `coverage`, and `missing_sources`.

7. Missing transcript or hook sources should be recorded explicitly and treated as a warning by default.

8. Validation should be able to fail when a task or lifecycle command requires complete transcript coverage.

9. Do not store full transcripts, raw event bodies, or large command outputs in `docs/plan`.

10. Keep generated-project and root policy semantically aligned.

11. Keep `raw_logs` as a backward-compatible aggregate list while adding named `transcript_log` and `hook_event_log` fields.

12. Model `coverage` as source-specific structured metadata for `external_transcript`, `codex_hooks`, and optional `manual_evidence`.

13. Treat missing sources as warnings by default; make them blocking only through `--require-transcript` or `--require-hooks`.

14. Make the manifest checker validate transcript structure and redaction status, but leave full secret scanning to transcript ingestion or security-specific checks.

15. Make hook manifest updates non-destructive so existing transcript metadata is preserved.

16. Keep the generated checker standalone and make the root checker delegate to the template implementation.

17. Allow transcript and hook event logs as compression inputs only after manifest and redaction review.

## Implementation Instructions

Update root and generated `SPEC_AGENT_LOGGING.md` with a hybrid logging model.

Define these log source roles:

- `external_transcript`: primary full-turn source provided by an outer runtime or API wrapper.
- `codex_hooks`: best-effort repo-local lifecycle and tool-event source.
- `manual_evidence`: optional manually added excerpts or artifacts, not a substitute for transcript coverage.

Define the expected transcript JSONL contract.

Each transcript record should include at least:

- `schema_version`
- `record_type`
- `created_at`
- `run_id`
- `turn_id`
- `role`
- `content`
- `metadata`

Allowed `role` values should include `user`, `assistant`, `tool`, and `system_event`.

Document that transcript ingestion must redact secrets before writing or must mark `redaction_status` for validator review.

Extend hook logging so `agent_log_event.py` updates `manifest.json` with `hook_event_log` and coverage metadata whenever it appends `raw/events.jsonl`.

Add a root `scripts/check-agent-log-manifest.py` and generated `template/scripts/check-agent-log-manifest.py`.

The checker should:

- validate required manifest keys;
- confirm referenced raw log paths exist when declared;
- detect transcript coverage from `transcript_log`;
- detect hook coverage from `hook_event_log`;
- report `missing_sources` consistently;
- support `--require-transcript`, `--require-hooks`, and `--self-test`.

Update `scripts/check-root-agent-policy.py` and `scripts/check-copier-template.py` so the new checker and policy references are required.

Update smoke tests to create sample manifests for:

- transcript and hooks both present;
- transcript present and hooks missing;
- hooks present and transcript missing;
- declared log path missing.

Keep all sample raw logs in temporary directories during tests or under ignored `.agent-logs/` paths.

Do not commit generated raw logs.

Update `SPEC_CONTEXT_COMPRESSION.md` only where needed to describe transcript and event logs as eligible compression inputs after manifest and redaction review.

Do not add a Copier prompt for this feature.

Generated projects should always receive the policy and checker because missing-source reporting is useful even when no external transcript runtime is installed.

## Tasks

- [x] Inspect current root and template hook logger behavior.
- [x] Define the hybrid manifest schema in root and generated logging policy.
- [x] Add root `scripts/check-agent-log-manifest.py`.
- [x] Add generated `template/scripts/check-agent-log-manifest.py`.
- [x] Update root and template hook loggers to write `hook_event_log`, `coverage`, and `missing_sources`.
- [x] Update context compression policy for transcript and hook event log inputs.
- [x] Update root policy checks and Copier template checks.
- [x] Update smoke tests for manifest coverage cases.
- [x] Update hook tests for manifest fields.
- [x] Run `python3 scripts/check-agent-log-manifest.py --self-test`.
- [x] Run `python3 scripts/check-copier-template.py`.
- [x] Run `scripts/lint-project-workflow.sh`.
- [x] Run `tests/smoke.sh`.
- [x] Run `tests/test-hooks.py`.
- [x] Run `git diff --check`.
- [x] Archive this plan after validation.

## Open Decisions

- None.

## Out Of Scope

- Do not implement a specific external Codex wrapper or API proxy in this plan.

- Do not store raw transcripts or hook events in Git-managed paths.

- Do not change the rule that active plans contain final decisions and summaries only.

- Do not require Headroom or another compression backend.

## Validation Notes

Validated with:

- `python3 scripts/check-agent-log-manifest.py --self-test`
- `python3 scripts/check-copier-template.py`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `tests/test-hooks.py`
- `git diff --check`

`tests/smoke.sh` emitted Copier `DirtyLocalWarning` because it rendered the template with uncommitted local changes, then passed.
