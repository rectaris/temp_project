# Project-Specific Copier Adoption

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - copier.yml
  - template/AGENTS.md.jinja
  - template/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/docs/agent/spec-index.yaml.jinja
  - template/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - template/docs/agent/external-services.yaml.jinja
  - scripts/check-copier-template.py
  - tests/fixtures/*.answers.yml
  - tests/smoke.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
checked_summary_ja: supportcard-status の高度な運用規則を維持したまま Copier 管理層を導入できるようにした。

## Summary

Added a generated `SPEC_COPIER_ADOPTION.md` and routed mature-repository Copier adoption through the generated spec index. External service documentation options now use mode-style Copier questions so projects can request documented MCP, Linear, and graph-memory policy without authorizing reads or writes.

## Decisions

- Use `mcp_policy_mode`, `linear_sync_mode`, and `graph_memory_mode` instead of resurrecting removed `use_*` activation booleans.
- Keep `document_optional` as documentation-only; generated services stay unauthorized until the project fills policy fields.
- Treat mature repositories as manual-merge targets for same-path files.

## Completed Work

- Added generated `docs/agent/SPEC_COPIER_ADOPTION.md`.
- Added `copier_adoption` routing to generated `spec-index.yaml`.
- Documented mature-repository external-service merge behavior.
- Added explicit external-service documentation modes to `copier.yml`.
- Updated fixture answers and smoke coverage for documented external-service states.

## Validation Notes

- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed. Copier emitted `DirtyLocalWarning` because the smoke test intentionally rendered the in-progress dirty template.
- `tests/copier-update.sh` passed. Copier emitted `DirtyLocalWarning` for the in-progress template.
- `git diff --check` passed.
