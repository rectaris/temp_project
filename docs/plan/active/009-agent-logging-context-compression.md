# Agent Logging and Context Compression

## Manifest

- `status`: `active`
- `task_type`: `planning_docs`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `copier.yml`
  - `README.md`
  - `template/AGENTS.md.jinja`
  - `template/docs/agent/spec-index.yaml.jinja`
  - `template/docs/agent/SPEC_AGENT_LOGGING.md`
  - `template/docs/agent/SPEC_CONTEXT_COMPRESSION.md`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/scripts/context-compress.sh`
  - `template/.gitignore`
  - `tests/`
- `required_specs`:
  - `AGENTS.md`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
- `acceptance`:
  - Generated projects document local agent raw logs without making raw logs a Git-managed source of truth.
  - Generated projects treat raw logs as retained local information assets and control reading through routing, indexes, and manifests.
  - Generated projects always have a context-compression policy that lets agents decide when to use available tooling.
  - Headroom is supported as an optional command-line backend, not as a required template dependency.
  - Normative routing and validation documents remain read as source text and are not compressed by default.
- `acceptance_focus`:
  - local-only forensic logs
  - route-based compression decisions
  - optional Headroom wrapper
- `expected_output`: template files, policy docs, and tests for agent logging and context compression.
- `checked_summary_ja`: 生成先にローカル agent ログ方針と任意の Headroom 対応 context 圧縮ルートを追加した。
- `completion_deferred_reason`: ``

## Goal

Add generated-project support for local agent raw logs and optional context compression.

The implementation must keep normal repository work local, deterministic, and dependency-light.

Headroom support is an optional backend that agents may use when it is already available on `PATH`.

Do not make Headroom a required dependency, and do not route normative project instructions through compression.

## Implementation Instructions

Implement this as generated agent policy plus a thin optional helper script.

Keep `docs/plan` as the long-term human and agent summary record.

Keep raw agent traces under `.agent-logs/` and large derived artifacts under `.agent-artifacts/`.

Keep both directories out of Git by default.

Treat raw logs as retained local information assets.

Do not add an automatic retention deadline.

Only delete raw logs through explicit cleanup or redaction flows.

Use routing, indexes, manifests, search, excerpts, and context compression to control what agents read back into context.

Do not control context size by deleting raw logs.

Store structured run metadata in `manifest.json`.

Use compressed outputs only as derived views.

The raw log remains the source evidence for audit and reproduction.

## Decisions

1. Always generate the agent logging policy and Git ignore rules.

2. Use fixed generated-project paths: `.agent-logs/` for raw logs and `.agent-artifacts/` for large artifacts.

3. Define raw logs as observable work evidence, including user requests, assistant-visible messages, tool calls, commands, stdout, stderr, diffs, validation output, and referenced paths when available.

4. Exclude or redact secrets, tokens, `.env` contents, unnecessary personal data, unavailable internal reasoning, and oversized binary payloads.

5. Require a minimal redaction report when raw logs are created or modified.

6. Keep raw logs by default.

7. Treat `docs/plan`-referenced runs as pinned.

8. Prevent accidental Git inclusion with both `.gitignore` and deterministic checks.

9. Use `manifest.json` as the standard run manifest format.

10. Add `scripts/context-compress.sh` as a single-file wrapper.

11. Make the wrapper refuse `AGENTS.md`, `docs/agent/`, validation specs, and security specs as compression inputs.

12. Save compressed outputs under the same run directory, for example `.agent-logs/<run-id>/compressed/`.

13. Add `SPEC_CONTEXT_COMPRESSION.md` as a generated policy that tells agents when to consider Headroom.

14. Use Headroom only when the `headroom` command is available.

15. Fall back to search, split reads, and excerpts when Headroom is unavailable.

16. Test the generated contract without installing Headroom.

## Tasks

- [ ] Inspect existing template outputs and smoke-test expectations.
- [ ] Add generated `.gitignore` entries for `.agent-logs/` and `.agent-artifacts/`.
- [ ] Add `SPEC_AGENT_LOGGING.md` covering raw logs, summaries, manifests, redaction, the default keep policy, explicit deletion, and Git boundaries.
- [ ] Add `SPEC_CONTEXT_COMPRESSION.md` covering route-based use of optional compression backends, including Headroom.
- [ ] Update `spec-index.yaml.jinja` with conditional routes for agent logging and context compression.
- [ ] Update `AGENTS.md.jinja` and development-flow docs so raw logs are local evidence, not the primary planning record.
- [ ] Add `context-compress.sh` as a thin fallback-safe wrapper around optional Headroom usage.
- [ ] Add deterministic checks for ignored raw-log paths and wrapper refusal paths.
- [ ] Update Copier generation tests and smoke tests.
- [ ] Run `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.

## Open Decisions

- None.

## Validation Notes

Confirm that generated projects receive no new required dependency.

Confirm that normal generated-project workflow, plan linting, and smoke tests pass when Headroom is not installed.
