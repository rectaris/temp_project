# Human Report Presentation

This specification governs local HTML views of developer-facing progress and decision reports.

## Authority And Storage

- Keep repository source files, Markdown plans, validation records, and Git history authoritative.
- Treat generated HTML as a disposable derived view.
- Write generated report files only below `.agent-artifacts/human-reports/`.
- Do not stage, commit, publish, or externally upload generated report files.
- Do not use `.agent-logs/`, `.agent-artifacts/`, `.git/`, credentials, private data, or unreviewed raw logs as report sources.

The managed `.project-agent-workflow/human-report.json` file selects either `disabled` or `agent_select_local` mode.

## When To Assess

Assess a human-facing progress or decision artifact when it contains at least one of these presentation signals:

- three or more alternatives that need comparison;
- three or more dependency, sequence, or impact relations;
- eight or more status and next-action items;
- cross-field comparison, filtering, or repeated scanning;
- an explicit user request for HTML.

Keep a short conclusion, a single decision, raw logs, normative policy, machine-readable indexes, and ordinary completion messages in text unless the user explicitly requests HTML.

## Structured Input

Create a temporary JSON input outside `.agent-logs/` and `.agent-artifacts/` with the exact contract enforced by `human-report.py`.

The input records:

- title, language, developer audience, progress or decision purpose, and summary;
- facts with `confirmed`, `inferred`, `unknown`, or `disputed` certainty and a declared source path;
- decision alternatives, relations, risks, and next actions;
- semantic presentation signals;
- a completed content-safety review with no raw logs or unredacted sensitive data;
- one or more repository-relative source paths.

Unknown fields, missing fields, unsupported enum values, unsafe source paths, and unresolved source files are errors.

## Commands

Print a complete example contract before drafting a new input:

```text
python3 .project-agent-workflow/scripts/human-report.py example
```

Assess before rendering:

```text
python3 .project-agent-workflow/scripts/human-report.py assess <report.json>
```

Render only when the assessment returns `decision: generate`:

```text
python3 .project-agent-workflow/scripts/human-report.py render <report.json> --report-id <lowercase-id>
```

The renderer writes `assessment.json` and `index.html` below `.agent-artifacts/human-reports/<lowercase-id>/`.

It escapes all report content, embeds its CSS, uses no JavaScript or external resources, and records the current Git commit and source-file hashes.

## User Communication

- Keep the chat response self-contained even when an HTML view is generated.
- Report the local HTML path and state that it is ignored and disposable.
- If assessment skips or blocks generation, continue with the normal text response and mention the reason only when it helps the reader.
- Never imply that a generated HTML view is current after any listed source hash changes.
