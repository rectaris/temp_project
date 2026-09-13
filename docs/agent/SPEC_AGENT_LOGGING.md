# Agent Logging

Agent logs are local evidence for audit, replay, debugging, and handoff work in this template development repository.

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

## Hybrid Log Sources

Use a hybrid model when multiple log sources are available:

- `external_transcript`: primary full-turn source provided by an outer runtime or API wrapper.
- `codex_hooks`: best-effort repo-local lifecycle and tool-event source.
- `manual_evidence`: optional manually added excerpts or artifacts, not a substitute for transcript coverage.

External transcript logs are primary for reconstructing user and assistant turns when available.
Codex hook logs corroborate lifecycle and tool activity but remain best-effort.

This repository owns the transcript ingestion contract and manifest validator.
It does not own a specific external capture runtime.

Transcript records are written to:

```text
.agent-logs/<run-id>/raw/transcript.jsonl
```

Each transcript JSONL record must include at least:

- `schema_version`
- `record_type`
- `created_at`
- `run_id`
- `turn_id`
- `role`
- `content`
- `metadata`

Allowed transcript `role` values are `user`, `assistant`, `tool`, and `system_event`.

Transcript ingestion must redact secrets before writing, or mark the transcript source with `redaction_status: "pending_review"` in `manifest.json`.

Use `scripts/import-codex-transcript.py` to normalize an external Codex session JSONL transcript into:

```text
.agent-logs/<run-id>/raw/transcript.jsonl
```

The importer updates `manifest.json`, `coverage.external_transcript`, and `redaction-report.md` through the template-owned `template/.project-agent-workflow/scripts/agent_log_manifest.py` shared manifest implementation.
It writes normalized transcript records, excludes reasoning content items, and defaults automatic redaction to `pending_review`.
Use `redacted` only after review or a deterministic project-specific check establishes that the stored data class is safe.

## Hook Logging

Use `scripts/agent-log-event.py` as the root best-effort logger for Codex lifecycle hook payloads when wiring hooks outside this read-only root `.codex/` environment.

Generated projects include `.codex/hooks/agent_log_event.py` and use it through `.codex/hooks.json` only when Codex hooks are enabled.

The hook records observable payloads for `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `PostCompact`, and `Stop` events.

For staged review, a runtime may emit `ReviewPacketStart` with the reviewer session id, the canonical review packet digest, and the inherited turn count. Only this explicit runtime event, or its normalized external-transcript equivalent, may establish review turn zero. `SessionStart` alone and caller-authored receipt fields do not establish it.

Hook logs are written to:

```text
.agent-logs/<run-id>/raw/events.jsonl
```

The hook also creates or updates `manifest.json` through the shared manifest implementation and maintains `redaction-report.md`.

On `Stop`, if Codex provides `transcript_path`, the hook attempts a best-effort call to `scripts/import-codex-transcript.py`.
This promotes the external transcript to the primary local source while keeping hook event logs as corroborating evidence.
If the path is unavailable or import fails, the hook must still succeed and the manifest must keep `external_transcript` in `missing_sources`.

Hook logging is best-effort and must not block agent execution.
Persist only allowlisted hook payload fields and mark automatic redaction as `pending_review`.
If the hook payload does not contain assistant final text, internal reasoning, or a full transcript, the hook must not reconstruct it.

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
  "plans": ["docs/plan/active/012-example.md"],
  "raw_logs": ["raw/session.log"],
  "transcript_log": null,
  "hook_event_log": null,
  "coverage": {
    "external_transcript": {
      "present": false,
      "path": null,
      "status": "missing",
      "redaction_status": "not_applicable"
    },
    "codex_hooks": {
      "present": false,
      "path": null,
      "status": "missing",
      "redaction_status": "not_applicable"
    }
  },
  "missing_sources": ["external_transcript", "codex_hooks"],
  "artifacts": [],
  "compressed_outputs": [],
  "redaction_report": "redaction-report.md",
  "pinned": false
}
```

Use stable relative paths.
Keep `raw_logs` as the backward-compatible aggregate list of declared raw log files.
Use `transcript_log` and `hook_event_log` for named hybrid source paths.
Use `coverage` for source-specific status metadata.
Use `missing_sources` to make absent transcript or hook sources explicit.
If a run is referenced by `docs/plan`, treat it as pinned.

Missing transcript or hook sources are warnings by default.
Validation may require complete transcript or hook coverage by using `scripts/check-agent-log-manifest.py --require-transcript` or `scripts/check-agent-log-manifest.py --require-hooks`.

## Resource Observations

Run manifests keep one bounded `resource_observations` object.

- Store provider token values only when the provider transcript directly reports input, cached input, output, or reasoning tokens.
- Store model-response, compaction, helper-turn, and tool-call counts only from directly observable records or deterministic proxy counting.
- Keep every unavailable value as `not_observed`; never estimate tokens or convert proxy counts into token claims.
- Store only the digest of a directly observed root-session identity.
- Bind each observation to the SHA-256 digest of the source evidence file that produced it. The `evidence_digests` object maps `external_transcript` and `codex_hooks` to the SHA-256 of the raw source file at the time observations were derived. The verifier recomputes each declared digest and rejects mismatches. Observed identity or metrics without at least one bound evidence digest are rejected.
- Bind a review turn-zero claim to one `ReviewPacketStart` observation whose session id, packet digest, inherited turn count, and source-file digest match the review receipt.
- Do not store prompts, response bodies, reasoning bodies, command bodies, environment values, or credentials in resource observations.

## Model Observations

Run manifests may keep one optional `model_observations` object. It is versioned independently of `resource_observations`, adds nothing to it, and is valid only when the run has at least one declared source file. A manifest without the object is valid legacy input.

Individual model statements stay on the records that reported them, as `metadata.model_observation` in `raw/transcript.jsonl` and `payload.model_observation` in `raw/events.jsonl`. The manifest object is a bounded derived summary of those records.

- Separate requested settings, runtime-reported settings, and provider-reported execution. `turn_context.model` and `turn_context.effort` are runtime-reported context. They do not establish that a caller requested the value or that a provider resolved and executed it, so the requested and provider-reported slots stay `not_observed` for the currently supported sources.
- Declare what each source shape can observe, and keep the producer and the reader on that one declaration. A transcript `turn_context` shape reports a runtime statement and its turn identity, a transcript `session_meta` shape reports provider context and a session identity, and a hook event reports a runtime statement and a session identity. The producer leaves an unavailable slot `not_observed`, the reader rejects a stored record that claims evidence its source shape cannot hold or that arrives in the wrong file, and such a record is reported as `unknown_source_shape` rather than silently skipped.
- Bind an observation to the shape its own record reports. A record reports one source shape, named by its record type, and an observation is read only when that type names the shape it claims. The record type is written by the source and read by unrelated parts of the importer, so a record cannot grant itself a shape it never reported, and a turn record cannot present its session's provider context as though the turn had reported it. A record whose observation does not match its reported shape is reported as `unknown_source_shape` and contributes nothing.
- The transcript and the hook log are the evidence of record. Verification establishes that the summary says exactly what those files say and that each record stays inside what its own shape can observe. It does not establish that the files themselves were never rewritten, so treat a source file as evidence only while its custody is intact.
- Reject a stored record whose shape drifted from the contract. An unexpected top-level field, and a stored value that the producer would have refused, each invalidate the whole record, so a hand-edited log cannot present unverified text as observed evidence.
- Keep `model_provider` and `cli_version` in `provider_context`. They describe the environment that reported a value; they are never proof that a provider executed a model.
- Preserve exact model identifiers. Never infer an alias snapshot, a default model, or a model from a role, profile, or agent name.
- Supported sources are the transcript `turn_context` and `session_meta` shapes and bounded hook `model` and `effort` values. An unrecognized record stays unobserved. Do not scan arbitrary nested objects or message bodies for model-looking strings.
- Retain `turn_id` and `root_turn_id` as distinct identifiers, and keep explicit parent links only where a source supplies them. A root turn id, a source-line fallback, or a timestamp never establishes a parent session or an actual turn, and the last observed model is never carried across a missing boundary, an independent session, a tool result, or a helper execution.
- Bind every statement to the source it came from: the recomputed SHA-256 of the evidence file, the record position within that file, and the original `source_line` where the source supplied one. Use hashed session identities in the summary.
- Verify the summary by recomputing it from the declared source files and requiring an exact match, not by checking the file digest alone. A matching digest proves only that the bytes are unchanged. Exact recomputation rejects a forged statement, a fabricated provider value and an inflated count, and equally rejects a summary that omits evidence the sources hold.
- Recompute the summary from the source records on every accepted update, so a repeated import or an appended hook log leaves no stale digest and no duplicate entry. Keep conflicting statements about the same scope available instead of choosing a winner.
- Bound the summary: at most 64 statements, at most 8 provider-context values per field, at most 128 characters per value, and at most 8 MiB per scanned source file. Report every bound that actually dropped evidence, so a consumer can tell bounded evidence from complete evidence. Report omitted, malformed, and unsupported evidence through the bounded diagnostic codes `malformed_value`, `unsupported_type`, `value_too_long`, `unknown_source_shape`, `statements_truncated`, `provider_context_truncated`, `source_unreadable`, `source_too_large`, `record_unparsable`, and `redacted_value`.
- Refuse a value instead of rewriting it. A secret, a redaction marker, a control character, and surrounding whitespace each make the value unusable, because a substituted marker or a trimmed string would publish an identifier no source reported. A refused value is also dropped from the raw record, so the allowlisted `model` and `effort` keys cannot retain unbounded or sensitive text.
- Report a declared source that is oversized, undecodable, or otherwise unreadable as `unreadable` with a null digest, zero counts, and no statements. Check the size before reading, so an oversized source costs no read. Evidence that cannot be bound to a digest is not recorded, and evidence from the sources that remain readable is kept.
- Persist no prompts, response bodies, reasoning bodies, command bodies, environment values, credentials, or external transcript paths in model observations. Hooks stay best-effort and never block execution; `scripts/check-agent-log-manifest.py` rejects a malformed or unbound record outright.
- A model observation is not a token count. `resource_observations` version 1 keeps its exact shape, counter interpretation, and totals, and no aggregate usage is reattributed to a model.
- Do not reimport or migrate existing logs to add model evidence. Missing evidence stays missing.



`scripts/summarize-agent-run.py` reports observed resources from explicitly supplied local records. It is advisory derived information, never acceptance, review, or validation evidence.

- Supply each record on the command line. The command discovers no session, reads no home directory, deletes no log, calls no model, and needs no network or external service.
- Supported inputs are run manifests, sandboxed-runner candidate manifests, and plan execution state records, read through their declared schema versions.
- The report is written to stdout only. Save it yourself under `.agent-logs/` or `.agent-artifacts/` when a run needs a durable copy.
- At most 32 explicit input files of at most 8 MiB each are accepted, and the report is bounded at 256 KiB. A symlinked, nonregular, oversized, or structurally invalid input is rejected before it is read further.
- Pass raw evidence with `--evidence` to bind a declared `evidence_digests` value to its source bytes. A supplied file that matches no declared digest, an unreadable supplied file, a malformed digest, an unsupported schema, and a malformed record each reject the whole report with a nonzero exit.
- Totals keep their unit and provenance. Provider token values and deterministic proxy counts are never merged, an observed zero stays a measurement, and a missing value stays `not_observed` instead of becoming zero.
- Runner duration, per-attempt duration, and ledger elapsed checkpoints are different measurement boundaries and stay in separate totals. Every total is reported beside its record coverage.
- Billed cost, human intervention, phase durations, replan counts, and total wall clock stay `not_observed` unless a supplied record observes them directly. The command performs no price lookup and no inference.

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
