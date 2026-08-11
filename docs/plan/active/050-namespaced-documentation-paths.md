# Align operational documentation with the namespaced generated layout

status: in_progress
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

- [ ] Correct the generated-project routing path in the root Skill.
- [ ] Correct generated lifecycle and validation helper paths in the planning and validation references.
- [ ] Correct the root AGENTS rule and Japanese-writing specification to name the existing template synchronization target.
- [ ] Add targeted static assertions for current managed paths and the removed stale path.
- [ ] Confirm that intentional project-owned `docs/agent/` and `template/docs/agent/` references remain intact.
- [ ] Run required static, generated-project, and repository validation.

## Validation Notes

Pending implementation.
