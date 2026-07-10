# Agent Log Hook

## Manifest

- `status`: `checked`
- `task_type`: `orchestration_meta`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `template/.codex/hooks.json`
  - `template/.codex/hooks/agent_log_event.py`
  - `template/docs/agent/SPEC_AGENT_LOGGING.md`
  - `scripts/agent-log-event.py`
  - `docs/agent/SPEC_AGENT_LOGGING.md`
  - `scripts/check-copier-template.py`
  - `scripts/check-root-agent-policy.py`
  - `tests/test-hooks.py`
  - `tests/smoke.sh`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_AGENT_LOGGING.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `git diff --check`
- `acceptance`:
  - Generated projects include a Codex `hooks.json` that wires logging for observable prompt, tool, compact, and stop events.
  - The hook writes local-only JSONL event logs, manifest, and redaction report under `.agent-logs/`.
  - The hook records observable payloads only and documents that full assistant text is limited by hook payload availability.
  - Root policy and checks recognize the hook.
  - Hook behavior tests cover prompt, tool, stop, and redaction behavior.
- `acceptance_focus`:
  - observable hook logging
  - local-only raw logs
  - generated-template coverage
- `expected_output`: hook script, hook config, docs, tests, and checked plan record.
- `checked_summary_ja`: Codex hook で観測可能な prompt/tool/stop event を `.agent-logs/` に保存する仕組みを追加した。
- `completion_deferred_reason`: ``

## Problem

The repository now has local raw-log policy and compression helpers, but no hook writes Codex lifecycle events to `.agent-logs/`.

## Goal

Add a deterministic Codex hook that records observable lifecycle event payloads as local raw evidence.

## Implementation Instructions

Use Codex hook events documented by the current Codex manual: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`, and `Stop`.

Write each event as a JSON line under `.agent-logs/<run-id>/raw/events.jsonl`.

Create or update `.agent-logs/<run-id>/manifest.json`.

Create a redaction report for each run.

Redact obvious secret-like values from payloads before writing.

Do not block agent execution from the logging hook. On errors, return an empty JSON object.

Document that hook logs capture only observable hook payloads; they may not contain unavailable internal reasoning or assistant final text when the hook payload does not provide it.

Add generated `template/.codex/hooks.json` so generated projects can discover the hook.

Because this repository root has an environment-provided read-only `.codex/` directory, add root script and policy checks but do not try to install root `.codex/hooks.json`.

## Decisions

1. Store hook logs under `.agent-logs/<run-id>/raw/events.jsonl`.

2. Use deterministic Python, not a shell pipeline, for redaction and JSON writing.

3. Configure generated-project hooks with `template/.codex/hooks.json`.

4. Root repository receives the hook script as `scripts/agent-log-event.py` and policy checks, but not a root `.codex/hooks.json`.

5. The hook is best-effort and must not block the agent loop.

## Tasks

- [x] Add generated hook config.
- [x] Add generated hook script.
- [x] Add root hook script.
- [x] Update root and template logging docs.
- [x] Add static required-file checks.
- [x] Add hook behavior tests.
- [x] Add smoke checks.
- [x] Validate and archive this plan.

## Open Decisions

- None.

## Validation Notes

Validated with:

- `python3 tests/test-hooks.py`
- `python3 scripts/check-root-agent-policy.py --self-test`
- `python3 scripts/check-copier-template.py`
- `git diff --check`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`

`tests/smoke.sh` emitted Copier `DirtyLocalWarning` because it rendered the template with uncommitted local changes, then passed.

The Codex manual hook section was used to confirm supported lifecycle events and `hooks.json` discovery.
