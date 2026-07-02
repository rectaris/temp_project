# Define skill authoring policy

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/spec-index.yaml
  - AGENTS.md
  - template/docs/agent/SPEC_SKILL_AUTHORING.md
  - template/docs/agent/spec-index.yaml.jinja
  - template/AGENTS.md.jinja
  - template/README.md.jinja
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/smoke.sh
target_json:
  - none
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Root and generated projects document how to create and update Codex skills.
  - Skill authoring tasks route to the new policy.
  - Template static checks and smoke tests cover the generated policy file.
expected_output: full-implementation
checked_summary_ja: skill作成方針をrootと生成テンプレートに追加した。

## Summary

Added root and generated-project skill authoring policy that defines skill placement, required files, naming, `SKILL.md` guidance, UI metadata, bundled resources, validation, and security boundaries.

## Decisions

- Store skill authoring policy under `docs/agent/`, not only in `references/`, because it is normative agent policy.
- Keep the policy concise and project-boundary oriented; do not copy the full generic skill-creator guide.
- Connect authoring policy to validation and optional SkillSpector checks.

## Completed Work

- Added `docs/agent/SPEC_SKILL_AUTHORING.md`.
- Added `template/docs/agent/SPEC_SKILL_AUTHORING.md`.
- Added `skill_authoring` routes to root and generated `spec-index.yaml`.
- Added AGENTS and generated README discovery text for skill authoring policy.
- Updated template and root policy checks to require the new spec.
- Added smoke coverage for generated skill authoring routes and policy links.

## Validation Notes

- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
