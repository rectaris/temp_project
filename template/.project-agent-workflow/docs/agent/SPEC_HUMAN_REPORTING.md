# Human Report Presentation

This specification governs local HTML views of developer-facing progress and decision reports.

## Authority And Storage

- Keep repository source files, Markdown plans, validation records, and Git history authoritative.
- Treat generated HTML as a disposable derived view.
- Write generated local report files only below `.agent-artifacts/human-reports/`.
- Do not stage, commit, publish, or externally upload generated local report files.
- Write shared team-facing report files only below `docs/human-report/`, and keep that path project owned.
- Do not use `.agent-logs/`, `.agent-artifacts/`, `.git/`, credentials, private data, or unreviewed raw logs as report sources.

The managed `.project-agent-workflow/human-report.json` file selects the local mode in `mode` and the shared publication mode in `shared_mode`.

`mode` is either `disabled` or `agent_select_local`. `shared_mode` is either `disabled` or `explicit_publish`. Each mode governs only its own output path.

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

## Shared Git-Managed Reports

A shared report is a reviewed project document that the team reads from the repository. It is not a raw agent artifact.

Publish one only when the team needs durable shared access. Keep using the local mode for disposable developer views.

### Storage And Reviewed Artifact

- `docs/human-report/<report-id>/report.json` is the reviewed structured source.
- `docs/human-report/<report-id>/index.html` is the derived publication file bound to that source.
- Review the structured source. Read the HTML, but do not hand-edit it; any edit fails the freshness validator.
- Publishing means writing these repository files. CI artifacts and hosted static sites are out of scope.

### Commands

Publish only when `shared_mode` is `explicit_publish`:

```text
python3 .project-agent-workflow/scripts/human-report.py publish <report.json> --report-id <lowercase-id>
```

Check every published report against the current repository bytes:

```text
python3 .project-agent-workflow/scripts/human-report.py verify-shared
```

`publish` writes the two files and stops. It never stages and never commits. A human reviews the diff, stages it, and commits it.

### Provenance And Freshness

Both published files record the generator version, the UTC generation time, the report id, the Git commit at publication, and every source path with its SHA-256.

`verify-shared` fails closed when a recorded source file is missing or no longer publishable, its current bytes hash differently, the published HTML is not the deterministic rendering of its structured source, a publication gate no longer holds, or a Git merge-conflict marker is present.

Never state that a published report is current without a passing `verify-shared` run.

### Retention, Supersede, And Conflicts

- Replace a published report only through `publish --supersede`, and record the replacement in an explicit supersede commit.
- Remove a published report only through an explicit human removal commit.
- Never prune published reports automatically.
- Resolve a merge conflict in a published file by hand and republish. Never overwrite an unresolved conflict.

### Publication Gates

Publication fails closed when the structured source or the rendered HTML shows any of:

- a missing content-safety review, raw logs, or unredacted sensitive data;
- secret-like material such as private keys or provider tokens;
- a source path outside the allowed evidence boundary;
- a script element, an event-handler attribute, a meta refresh, or an external reference attribute;
- an embedded stylesheet that imports or loads an external resource;
- a missing document language, top-level heading, embedded stylesheet, scoped row header, column header, or print layout.

### Copier Boundary

Copier manages the generator, this policy, the configuration, and the validator. It never manages `docs/human-report/`, so a Copier update never replaces or removes a published team report.

### Automatic Commits

Automatic commits are not implemented. `human_report_shared_mode` is the project configuration that would carry that authority, and enabling it requires a separate approved plan.

## User Communication

- Keep the chat response self-contained even when an HTML view is generated.
- Report the local HTML path and state that it is ignored and disposable.
- Report a shared report path and state that it is Git tracked and awaiting human review, staging, and commit.
- If assessment skips or blocks generation, continue with the normal text response and mention the reason only when it helps the reader.
- Never imply that a generated HTML view is current after any listed source hash changes.
