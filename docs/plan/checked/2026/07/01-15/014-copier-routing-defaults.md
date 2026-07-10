# Copier Routing Defaults

## Manifest

- `status`: `checked`
- `task_type`: `template_workflow`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `copier.yml`
  - `template/AGENTS.md.jinja`
  - `template/docs/agent/spec-index.yaml.jinja`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `template/docs/agent/SPEC_VALIDATION.md.jinja`
  - `scripts/check-copier-template.py`
  - `tests/fixtures/*.answers.yml`
  - `tests/smoke.sh`
  - `tests/copier-update.sh`
- `required_specs`:
  - `AGENTS.md`
  - `docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `docs/agent/SPEC_DECISION_AUDIT.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
  - `git diff --check`
- `acceptance`:
  - Copier no longer prompts for local-only workflow modules that agents can activate through text routing.
  - Generated projects still include the local workflow files needed for plan lifecycle, change validation, static security checks, structure scanning, helper agents, and concurrency guidance.
  - Runtime policy tells agents to decide whether to read or execute those local modules through `docs/agent/spec-index.yaml` and routed specs.
  - Hook, SkillSpector, and external-service activation are left unchanged by this plan and are redesigned only by `docs/plan/active/015-copier-activation-modes.md`.
  - Static checks, fixtures, smoke tests, and update tests match the reduced Copier question set.
- `acceptance_focus`:
  - reduced Copier prompts
  - route-based runtime activation
  - explicit external opt-ins
  - template update compatibility
- `expected_output`: reduced Copier question set, updated generated policy text, updated checks and fixtures, validation output, and checked plan record.
- `checked_summary_ja`: ローカル完結の workflow module を Copier 質問から外し、生成後の agent routing で使用判断する方針に整理した。
- `completion_deferred_reason`: ``

## Problem

`copier.yml` currently asks for several local workflow settings that do not need generation-time user choice.

The generated repository can include these local workflow modules by default and let agents decide whether to read or run them through text routing.

Keeping these settings as Copier questions increases setup friction and creates fixture and update churn without giving the user a meaningful safety boundary.

## Goal

Reduce Copier prompts by removing only local-only workflow module questions.

Make local workflow modules default-on in generated repositories.

Use generated agent routing policy to decide when those modules are relevant during task execution.

Leave hook behavior, SkillSpector behavior, and external-service activation semantics to `docs/plan/active/015-copier-activation-modes.md`.

## Decisions

1. Remove generation-time questions for local-only workflow modules that can be safely installed by default.

2. Keep `project_name`, `project_slug`, `project_purpose`, and `primary_language` as descriptive Copier prompts.

3. Do not redesign hook, SkillSpector, MCP, Linear, or graph-memory answers in this plan.

4. Preserve `.copier-answers.yml` update compatibility by making removed settings internal defaults or by providing a documented migration path for older answers.

5. Do not remove generated local workflow files as part of this work.

6. Keep `planning_style` as generated metadata with the fixed value `active_backlog_checked`.

7. Keep Codex helper-agent concurrency as generated config with `max_threads = 4`.

## Implementation Instructions

Remove these Copier questions if no later inspection shows a hard generation-time boundary:

- `planning_style`
- `use_codex_agents`
- `max_agent_threads`
- `use_plan_lifecycle`
- `use_change_validation`
- `use_security_static`
- `use_structure_scanner`

Replace removed answers with internal template defaults where templates still need values.

Use defaults equivalent to the current recommended path:

- `planning_style`: `active_backlog_checked`
- `use_codex_agents`: `true`
- `max_agent_threads`: `4`
- `use_plan_lifecycle`: `true`
- `use_change_validation`: `true`
- `use_security_static`: `true`
- `use_structure_scanner`: `true`

Do not preserve `false` values for removed answers from older `.copier-answers.yml` files.

After this change, older generated repositories may still retain obsolete keys in `.copier-answers.yml`, but the template must not read them.

Keep these Copier questions:

- `project_name`
- `project_slug`
- `project_purpose`
- `primary_language`

Leave these current answers untouched for plan 015 to replace with modes or generated policy states:

- `use_hooks`
- `use_skillspector`
- `use_mcp_policy`
- `use_linear_sync`
- `use_graph_memory`

Update generated `AGENTS.md` and generated agent docs so they no longer present removed local workflow defaults as user-selected template answers.

Add or update policy text stating that local workflow modules are available by default and should be used only when the task route requires them.

Update `scripts/check-copier-template.py` so `QUESTIONS` removes only the local-only workflow questions listed above and any required internal defaults are checked directly.

Update all Copier answer fixtures to remove only the deleted local-only workflow answers.

Update smoke and update tests for the reduced local-only prompt set and confirm generated required files still exist.

Inspect Copier update behavior from old answer files before finalizing.

If removed answers from an older `.copier-answers.yml` cause update failures or rejection churn, add the smallest compatible handling supported by Copier and document it in the plan's validation notes.

## Tasks

- [x] Inspect all template references to the removable Copier answers.
- [x] Convert removable answers to internal defaults or static generated text.
- [x] Update generated agent routing and development-flow policy for route-based local module use.
- [x] Reduce `scripts/check-copier-template.py` question checks.
- [x] Update answer fixtures and smoke/update expectations for local-only question removal.
- [x] Run template static checks.
- [x] Run `scripts/lint-project-workflow.sh`.
- [x] Run `tests/smoke.sh`.
- [x] Run `tests/copier-update.sh` if Copier is available.
- [x] Archive this plan after validation.

## Out Of Scope

- Do not replace `use_hooks`, `use_skillspector`, `use_mcp_policy`, `use_linear_sync`, or `use_graph_memory`; plan 015 owns those changes.

- Do not change external-service policy semantics or hook activation modes; plan 015 owns those changes.

## Open Decisions

- None.

## Validation Notes

Validated with:

- `python3 scripts/check-copier-template.py`
- `git diff --check`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `tests/copier-update.sh`

`tests/smoke.sh` and `tests/copier-update.sh` emitted Copier `DirtyLocalWarning` because they rendered the template with uncommitted local changes, then passed.

Copier update from `v0.2.0` passed without rejection files after removing local-only workflow questions.
