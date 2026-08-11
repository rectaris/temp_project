# Align operational documentation with the namespaced generated layout

status: checked
task_types:
  - japanese_prose
  - skill_authoring
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - AGENTS.md
  - SKILL.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/
  - references/planning.md
  - references/validation.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
context_files:
  - copier.yml
  - template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - template/.project-agent-workflow/scripts/
  - template/docs/agent/
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Route reusable generated-project policy and helper commands to .project-agent-workflow while retaining intentional project-owned docs/agent references.
  - Point the root Japanese-writing synchronization rule to the existing namespaced template specification.
  - Remove stale pre-namespace paths only from current operational guidance, without rewriting historical checked plans.
  - Add deterministic checks for the required current paths and the forbidden stale synchronization path.
  - Keep generated template content unchanged unless a current generated document itself contains a stale path.
checked_summary_ja: 現行生成レイアウトに合わせて Skill、参照文書、日本語方針のパスを名前空間付き管理領域へ修正する。

## Context

Operational documentation must distinguish root package paths from the namespaced managed paths generated under .project-agent-workflow.

The current Skill and references name pre-namespace helper locations, and the root Japanese-writing policy points to a template path that no longer exists.

## Decisions

- Use `.project-agent-workflow/docs/agent/` and `.project-agent-workflow/scripts/` for reusable managed content in generated repositories.
- Keep `docs/agent/` references when they intentionally identify project-owned extensions.
- Correct the Japanese-writing synchronization target to `template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` without forcing semantic identity between the intentionally different root and generated policies.
- Implement this plan before plans 051 and 052 so their checks and orchestration wording use the final paths.

## Tasks

- [x] Correct the generated-project routing path in the root Skill.
- [x] Correct generated lifecycle and validation helper paths in the planning and validation references.
- [x] Correct the root AGENTS rule and Japanese-writing specification to name the existing template synchronization target.
- [x] Add targeted static assertions for current managed paths and the removed stale path.
- [x] Confirm that intentional project-owned `docs/agent/` and `template/docs/agent/` references remain intact.
- [x] Run required static, generated-project, and repository validation.

## Validation Notes

- The root Skill and its planning and validation references now route reusable generated-project policy and helpers through `.project-agent-workflow/`.
- The root AGENTS rule and Japanese-writing specification now point to the existing namespaced template specification while preserving intentional project-owned `docs/agent/` references.
- Both root static checkers require the current managed paths and reject the removed Japanese-writing synchronization path and selected pre-namespace helper paths.
- `python3 scripts/check-copier-template.py`, `python3 scripts/check-root-agent-policy.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed with pinned actionlint 1.7.12 available on `PATH`.
