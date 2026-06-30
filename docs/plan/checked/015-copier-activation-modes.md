# Copier Activation Modes

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `copier.yml`
  - `template/AGENTS.md.jinja`
  - `template/README.md.jinja`
  - `template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja`
  - `template/docs/agent/SPEC_VALIDATION.md.jinja`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `template/docs/agent/spec-index.yaml.jinja`
  - `scripts/check-copier-template.py`
  - `tests/fixtures/*.answers.yml`
  - `tests/smoke.sh`
  - `tests/copier-update.sh`
- `related_checked_plans`:
  - `docs/plan/checked/014-copier-routing-defaults.md`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `tests/copier-update.sh`
  - `git diff --check`
- `acceptance`:
  - Copier keeps descriptive text inputs for project identity, purpose, and primary language.
  - Boolean prompts that remain after plan 014 are limited to hook, SkillSpector, and external-service activation and are replaced with explicit modes or generated disabled policy blocks.
  - Generated repositories do not treat a reflexive yes/no answer as authorization for hooks, external writes, persistent memory writes, or external-tool execution.
  - External-service configuration requires generated project-local policy fields for connection names, credential names, read/write boundaries, and write authorization rules.
  - Backward compatibility for existing `.copier-answers.yml` boolean answers is tested or explicitly documented.
  - Static checks, fixtures, smoke tests, and update tests match the new mode-based interface.
- `acceptance_focus`:
  - mode-based Copier interface
  - no implicit external side effects
  - generated project-local activation policy
  - update compatibility
- `expected_output`: mode-based Copier questions, generated activation policy docs, updated fixtures and tests, validation output, and checked plan record.
- `checked_summary_ja`: Copier の yes/no 質問を mode と生成後 policy 設定に置き換え、反射的な yes で外部副作用が有効にならない設計へ移行した。
- `completion_deferred_reason`: ``

## Problem

The user wants to keep the existing descriptive Copier inputs, but avoid relying on yes/no prompts for settings where users may select `yes` reflexively.

The current boolean prompts mix several meanings:

- install files
- document optional policy
- enable local runtime behavior
- imply external-service readiness

Those meanings have different risk levels.

Treating them as boolean answers can make generated projects look more enabled than they actually are.

## Goal

Keep descriptive Copier prompts for project facts.

Replace remaining yes/no prompts with explicit modes or generated disabled policy sections.

Make local installation, runtime activation, external reads, external writes, and persistent-memory writes separate states.

Assume plan 014 owns local-only workflow question removal.

Do not rework `planning_style`, `use_codex_agents`, `max_agent_threads`, `use_plan_lifecycle`, `use_change_validation`, `use_security_static`, or `use_structure_scanner` except to account for their already-removed defaults.

## Decisions

1. Keep `project_name`, `project_slug`, `project_purpose`, and `primary_language` as Copier prompts.

2. Replace hook boolean behavior with `codex_hooks_mode`.

3. Replace SkillSpector boolean behavior with `skillspector_mode`.

4. Replace external-service booleans with generated service state fields in project-local policy.

5. Default external services to disabled and require project-local configuration before reads or writes.

6. Write-capable external operations must require explicit user intent or a documented lifecycle command even after a service is configured.

7. Preserve update compatibility for old boolean answers during migration.

8. Generate `.codex/hooks.json` only for `codex_hooks_mode: enable_local_logging`.

9. Keep hook scripts under `.codex/hooks/` for `install_templates`; the inactive/active boundary is the generated `.codex/hooks.json` file.

10. Map old `use_hooks: true` answers to `codex_hooks_mode: install_templates` and old `use_hooks: false` answers to `codex_hooks_mode: disabled`.

11. Map old `use_skillspector: true` answers to `skillspector_mode: document_optional` and old `use_skillspector: false` answers to `skillspector_mode: disabled`.

12. Map old external-service `true` answers to `documented` and old `false` answers to `disabled`.

13. Store generated external-service states in a machine-readable project-local policy file and keep `documented` read/write-disabled.

## Implementation Instructions

Coordinate with `docs/plan/checked/014-copier-routing-defaults.md`.

Implement plan 014 first or in the same branch before final validation so local-only workflow booleans are removed once and are not redesigned here.

Keep these descriptive Copier prompts as they are unless a separate user decision changes them:

- `project_name`
- `project_slug`
- `project_purpose`
- `primary_language`

Replace `use_hooks` with a string mode:

```yaml
codex_hooks_mode:
  type: str
  choices:
    - disabled
    - install_templates
    - enable_local_logging
  default: install_templates
```

Define hook mode behavior as follows:

- `disabled`: do not generate executable hook configuration; generated docs may mention how to add hooks later.
- `install_templates`: generate hook scripts and documentation, but do not generate an active `.codex/hooks.json`.
- `enable_local_logging`: generate `.codex/hooks.json` and local logging hook wiring.

For old answers, map `use_hooks: true` to `install_templates` and `use_hooks: false` to `disabled`.

Replace `use_skillspector` with a string mode:

```yaml
skillspector_mode:
  type: str
  choices:
    - disabled
    - document_optional
  default: disabled
```

Do not run SkillSpector from generated validation automatically.

Document the scan command only when `skillspector_mode` is `document_optional`.

For old answers, map `use_skillspector: true` to `document_optional` and `use_skillspector: false` to `disabled`.

Replace `use_mcp_policy`, `use_linear_sync`, and `use_graph_memory` as Copier booleans.

Generated projects should contain external-service policy in a disabled state by default.

For old answers, map old external-service `true` values to `documented` and old `false` values to `disabled`.

Use project-local policy fields such as:

```yaml
external_services:
  mcp:
    state: disabled
  linear_sync:
    state: disabled
  graph_memory:
    state: disabled
```

When documenting the configured shape, require at least these fields before use:

- service state
- connection or workspace identifier
- credential environment variable name
- allowed read operations
- allowed write operations
- write authorization rule
- dry-run or local validation behavior
- fallback behavior when the service is unavailable

Use state names that avoid implying side effects from documentation alone.

Recommended states:

- `disabled`
- `documented`
- `configured_read_only`
- `configured_write_capable`

Ensure `documented` means policy text exists but service reads and writes are not authorized.

Generate a machine-readable project-local policy file for these states and have prose specs point agents to it before external reads or writes.

Update `template/AGENTS.md.jinja` so generated settings no longer display external-service booleans as enabled features.

Update `template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja` so agents must inspect the generated policy state and required fields before using MCP, Linear, or graph memory.

Update `template/docs/agent/SPEC_VALIDATION.md.jinja` so SkillSpector is optional documentation, not an enabled boolean check.

Update static checks and fixtures for renamed questions and removed booleans.

Add update-test coverage from old answer files containing `use_hooks`, `use_skillspector`, `use_mcp_policy`, `use_linear_sync`, or `use_graph_memory`. The update test must verify that old booleans do not leave active hooks enabled, do not leave old boolean labels in generated docs, and do not configure external services beyond `documented`.

Do not add duplicate coverage for local-only workflow booleans when plan 014 already covers them.

If Copier cannot map old boolean answers cleanly, document the manual migration in the generated README and in validation notes.

## Tasks

- [x] Confirm plan 014's local-only question removal is already implemented or included in the same branch.
- [x] Replace `use_hooks` with `codex_hooks_mode`.
- [x] Replace `use_skillspector` with `skillspector_mode`.
- [x] Replace external-service booleans with generated disabled policy states.
- [x] Update generated `AGENTS.md` settings language.
- [x] Update generated validation and external-service specs.
- [x] Update `scripts/check-copier-template.py`.
- [x] Update answer fixtures.
- [x] Add or update migration/update coverage for old boolean answers.
- [x] Run `scripts/lint-project-workflow.sh`.
- [x] Run `tests/smoke.sh`.
- [x] Run `tests/copier-update.sh`.
- [x] Run `git diff --check`.
- [x] Archive this plan after validation.

## Open Decisions

- None.

## Out Of Scope

- Do not remove local-only workflow Copier questions here; plan 014 owns that work.

- Do not change route-based local workflow activation rules except where references need to match plan 014's final defaults.

## Validation Notes

Validated with:

- `python3 scripts/check-copier-template.py`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `tests/copier-update.sh`
- `git diff --check`

`tests/smoke.sh` and `tests/copier-update.sh` emitted Copier `DirtyLocalWarning` because they rendered the template with uncommitted local changes, then passed.

`tests/copier-update.sh` covers legacy activation booleans from `v0.4.1`: old `use_hooks: true` migrates to `codex_hooks_mode: install_templates`, old `use_skillspector: true` migrates to `skillspector_mode: document_optional`, and old external-service `true` answers migrate to `documented` without configuring reads, writes, or active hooks.
