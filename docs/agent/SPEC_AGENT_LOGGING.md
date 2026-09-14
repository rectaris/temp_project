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
- Fail a malformed input record, and an aggregate that cannot be rendered, with a bounded error rather than an unhandled exception. Write the report as the bytes already checked against the output bound, so the encoding the surrounding environment configured for the output stream cannot turn a valid report into an unhandled failure.
- Fail a malformed input record with a bounded error rather than an unhandled exception. Nesting depth and numeric length are attacker controlled within the input bound, and a number can be valid JSON yet too large to represent, so refusing them is part of reading the record, not an internal fault.
- Supported inputs are run manifests, sandboxed-runner candidate manifests, and plan execution state records, read through their declared schema versions.
- The report is written to stdout only. Save it yourself under `.agent-logs/` or `.agent-artifacts/` when a run needs a durable copy.
- At most 32 explicit input files of at most 8 MiB each are accepted, and the report is bounded at 256 KiB. A symlinked, nonregular, oversized, or structurally invalid input is rejected before it is read further.
- Pass raw evidence with `--evidence` to bind a declared `evidence_digests` value to its source bytes. A supplied file that matches no declared digest, an unreadable supplied file, a malformed digest, an unsupported schema, and a malformed record each reject the whole report with a nonzero exit.
- Totals keep their unit and provenance. Provider token values and deterministic proxy counts are never merged, an observed zero stays a measurement, and a missing value stays `not_observed` instead of becoming zero.
- Runner duration, per-attempt duration, and ledger elapsed checkpoints are different measurement boundaries and stay in separate totals. Every total is reported beside its record coverage.
- Billed cost, human intervention, phase durations, replan counts, and total wall clock stay `not_observed` unless a supplied record observes them directly. The command performs no price lookup and no inference.
- The report carries a `model_evidence` section when a supplied run manifest declares `model_observations`. A manifest written before that contract is valid input and is counted as carrying none.
- Report requested, runtime-reported, and provider-reported statements separately, each beside its source kind, its execution identity, its source coverage, and the record position it came from. Carry that provenance in every supported output format, because a reader of the default format has to be able to reach the record that made the claim.
- Verify a summary by rebuilding the whole object with the producer that wrote it and requiring an exact match, not by checking the file digest alone. A matching digest proves only that the bytes are unchanged; it cannot detect a forged statement, a fabricated provider value, an inflated count, a forged diagnostic, or a summary that omits evidence the sources hold. Rebuilding with the producer also keeps its ordering, deduplication, truncation, and identity counting authoritative instead of reimplementing them in the reader, so bounded producer output still verifies.
- Verify per manifest, all or nothing. A summary is derived from every declared source together, so one missing source leaves nothing to check the remainder against. A manifest is reported as `recomputed` only when every declared source was supplied with `--evidence` and the rebuild matched exactly; otherwise every reported model component stays `declared_only`, which is an unverified claim. A rebuild that differs rejects the whole report, and supplied evidence that cannot be rescanned is rejected rather than reported.
- Take the source set from the manifest's own declared source files, not from the digests the summary happens to carry. A summary that omits a declared source names fewer sources than the producer read, so rebuilding it would confirm a narrower claim than the manifest makes, and a declared source the producer could not read leaves no bytes to rebuild from. Either way the manifest stays an unverified claim rather than a rejected one.
- Preserve the manifest's source-path relationships when rebuilding. Two source kinds naming one file were read as one file, so rebuilding them as two would confirm a run that could not have happened, and one path declared with two digests describes a run that could not have happened either.
- Rebuild from the bytes whose digest was verified, not from the supplied path. Rereading a path after hashing it would let a file that changed in between bind one version's statements to another version's digest, so the reader rebuilds against a private snapshot of those exact bytes, which also holds the rescan inside the bound the bytes already satisfied.
- Label every reported model component with the verification state of the manifest it came from, including a source the summary carries no digest for, and record a deduplicated statement against each manifest that supplied it. A verification label states what a manifest was checked against, so absence belongs to the coverage status and the missing digest instead. A statement collapsed across manifests otherwise takes the label of whichever manifest happened to be read first.
- Compare a rebuilt value to a declared value by type as well as by value, because `true` and `1`, or `1` and `1.0`, would otherwise pass as an exact match for a value the producer could never have written.
- Bind a statement to the file that can hold its shape. A source kind is readable from exactly one container, so a statement pairing a shape with an evidence source that never holds it names a record that could not exist and is rejected.
- Repeat every producer refusal on read. A stored value matching the producer's secret patterns, a redaction marker, a control character, a padded identifier, or an overlong string is rejected rather than reported, and report text that cannot be encoded rejects the report instead of failing unhandled. Those patterns recognize known credential shapes rather than every secret, so the refusal bounds what a stored value may look like and never certifies that a reported value carries no sensitive content.
- Refuse text that would corrupt or spoof the rendered report, in a record identifier as well as in an observed value. The report is line oriented, so an embedded newline forges a report line, a Unicode line or paragraph separator forges one for any reader that honours it, and a Unicode formatting character such as a bidirectional override reorders what a reader sees.
- Confirm an execution scope only from a shape that names a turn. One session reports many executions, so a session identity alone does not make two statements comparable.
- Call two statements incompatible only when they state different values for the same attribute and evidence class within the same confirmed execution scope, or at the same record position in the same source bytes. A statement whose scope is unconfirmed is counted and named, never compared against an unrelated turn or session. Different turns reporting different models are not a conflict.
- Deduplicate by source digest, record position, and the whole claim a statement makes, so the same record supplied through several manifests is counted once while two manifests making different claims about one record stay separately visible and are reported as a record-position conflict.
- Reject a statement that names a source with no evidence digest, because nothing could ever verify or refute it.
- Bind each statement to what its own source shape can observe. A shape reports only its declared evidence classes and its declared execution identities, so a runtime context statement can never arrive as a requested or provider-confirmed one, and a session-scoped shape can never name a turn. A statement that claims either is rejected.
- `resource_observations` version 1 totals, provenance, maxima, coverage, and input limits stay exactly as they were. A model statement names an observed model, never its resource usage, so `per_model_token_totals`, `per_model_billed_cost`, and `per_model_completed_task_counts` are reported as unavailable rather than derived by dividing a run-wide total across model names.

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
