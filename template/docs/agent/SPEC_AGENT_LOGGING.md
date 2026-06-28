# Agent Logging

## Purpose

Agent logs are local evidence for audit, replay, debugging, and handoff work.

They do not replace `docs/plan`. Keep plans as the durable summary and decision record. Use logs as source evidence that a plan, review, or later agent can reference by run id when deeper inspection is needed.

## Paths

- `.agent-logs/`: raw run logs, manifests, redaction reports, and derived compressed views.
- `.agent-artifacts/`: large local artifacts produced or collected during agent work.

Both paths are local-only and ignored by Git by default.

## Raw Log Scope

Raw logs should capture observable work evidence when available:

- user requests and assistant-visible messages;
- tool calls, commands, stdout, stderr, and exit status;
- changed paths, diffs, validation commands, and validation output;
- referenced files, plans, issue ids, URLs, or external task ids;
- follow-up decisions and unresolved risks.

Do not invent or reconstruct missing internal reasoning. Record what is observable.

## Hook Logging

Generated projects include `.codex/hooks/agent_log_event.py` and `.codex/hooks.json`.

When Codex hooks are enabled, the hook records observable payloads for `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`, and `Stop` events.

Hook logs are written to:

```text
.agent-logs/<run-id>/raw/events.jsonl
```

The hook also creates or updates `manifest.json` and `redaction-report.md`.

Hook logging is best-effort and must not block agent execution. If the hook payload does not contain assistant final text, internal reasoning, or a full transcript, the hook must not reconstruct it.

## Exclusions And Redaction

Never store credentials, tokens, private keys, `.env` contents, or deployment secrets in raw logs.

Redact unnecessary personal data, secret-bearing environment values, unavailable internal reasoning, and oversized binary payloads. For binaries or very large generated outputs, store a path, digest, size, and short description instead of inline content.

When creating or modifying raw logs, add or update a minimal redaction report for the run. The report should state what was excluded, what was redacted, and whether any secret-like content required manual review.

## Manifest

Each run directory should include `manifest.json` when practical:

```json
{
  "run_id": "20260628T120000Z-example",
  "created_at": "2026-06-28T12:00:00Z",
  "task": "short task label",
  "plans": ["docs/plan/active/009-example.md"],
  "raw_logs": ["raw/session.log"],
  "artifacts": [],
  "compressed_outputs": [],
  "redaction_report": "redaction-report.md",
  "pinned": false
}
```

Use stable relative paths. If a run is referenced by `docs/plan`, treat it as pinned.

## Retention

Keep raw logs by default. Do not add an automatic retention deadline.

Delete logs only through an explicit cleanup or redaction flow. Before deleting a run, check whether it is referenced by `docs/plan`, `docs/plan/checked.md`, an active issue, or another durable project record.

## Reading Policy

Agents must not load raw logs by default. Use `docs/agent/spec-index.yaml` routing, `manifest.json`, filenames, search, and targeted excerpts to decide what to read.

Prefer reading:

1. plan summaries and checked records;
2. run manifests and redaction reports;
3. targeted raw-log excerpts;
4. compressed derived views for large logs;
5. full raw logs only when the task requires source evidence.

Raw logs are retained information assets. Context size is controlled by routing and targeted reads, not by deleting evidence.

## Git Boundary

Do not commit `.agent-logs/` or `.agent-artifacts/`.

If durable evidence must become repository history, summarize it in `docs/plan` or another reviewed document. Do not move raw logs into Git-managed paths unless the repository owner explicitly requests that and the content has passed redaction review.
