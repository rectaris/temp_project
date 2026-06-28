# Context Compression

## Purpose

Context compression creates derived views of large local evidence so agents can inspect enough signal without loading full logs or artifacts into context.

Compression is optional. It must never become a required dependency for normal repository work.

## Non-Compressed Sources

Do not use context compression for normative project instructions:

- `AGENTS.md`;
- `docs/agent/`;
- validation policy;
- security policy;
- active task instructions that must be followed exactly.

Read those files as source text through the routing rules in `docs/agent/spec-index.yaml`.

## Eligible Inputs

Consider compression for:

- large raw logs under `.agent-logs/`;
- long CI logs;
- large stdout or stderr captures;
- verbose JSON, trace, or telemetry dumps;
- large generated text artifacts under `.agent-artifacts/`.

Before compressing, check the run `manifest.json` and redaction report when they exist.

## Decision Flow

1. Read the active plan or task summary first.
2. Use `spec-index.yaml` to decide whether agent logging or context compression policy applies.
3. Inspect `manifest.json`, filenames, and search results before opening large files.
4. Use targeted excerpts when they answer the question.
5. Use `scripts/context-compress.sh` when the input is too large for direct review.
6. Treat compressed output as a derived view. Return to the raw log for audit-critical claims.

## Headroom

Headroom is an optional backend. Use it only when the `headroom` command is already available on `PATH`.

Do not install Headroom automatically, add it as a required package dependency, or fail normal workflow because it is unavailable.

When Headroom is unavailable or fails, fall back to search, split reads, targeted excerpts, or the built-in fallback output from `scripts/context-compress.sh`.

## Wrapper

Use:

```sh
scripts/context-compress.sh <input-file> [run-id]
```

The wrapper writes compressed output under:

```text
.agent-logs/<run-id>/compressed/
```

Set `HEADROOM_DISABLED=1` to force the deterministic fallback path during tests or debugging.

The wrapper refuses normative instruction files and policy paths that should be read directly.

## Output Use

Compressed files may be cited in handoffs or plan notes as local derived views, but the raw log remains the source evidence.

If a compressed view is used to make a durable decision, include the run id and the raw source path in the plan or checked record.
