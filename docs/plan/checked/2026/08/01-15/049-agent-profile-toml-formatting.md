# Accept valid customized TOML formatting during agent profile normalization

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - docs/plan/
  - scripts/update_agent_model_profiles.py
  - tests/copier-update.sh
  - tests/test-agent-model-profiles.py
context_files:
  - copier.yml
  - docs/plan/checked/2026/08/01-15/042-agent-profile-update-task.md
  - template/.project-agent-workflow/ownership.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-agent-model-profiles.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Replace indented top-level model and model_reasoning_effort keys that are valid under the supported TOML parser, and recognize indented name and description keys only as insertion anchors.
  - Change only model and model_reasoning_effort values while preserving project-owned instructions, comments, unrelated fields, line order, and formatting outside the replaced fixed fields.
  - Keep repeated normalization idempotent.
  - Continue to stop on invalid TOML, semantic duplicate fields, missing built-in profiles, and symlinked profile files.
  - Cover the customized-whitespace behavior through focused unit tests and a representative Copier update path.
checked_summary_ja: agent profile の有効な TOML 空白表記を保持しながら、固定対象のモデル 2 項目だけを安全に正規化する。

## Context

The agent profile normalizer must accept supported TOML whitespace while changing only the two template-fixed model fields.

The current parser accepts an indented top-level key, but the subsequent line matcher misses it and inserts a duplicate key during Copier copy or update.

## Decisions

- Keep line-preserving normalization rather than reserializing the complete TOML document.
- Make fixed-field and insertion-anchor detection aware of TOML-permitted leading whitespace.
- Preserve the fail-closed behavior established by checked plan 042.
- Convert every post-render parse failure into the normal controlled profile error instead of exposing an uncaught parser exception.

## Tasks

- [x] Make fixed-field and insertion-anchor matching accept supported leading whitespace without broadening the editable field set.
- [x] Add tests for indented existing fields, indented insertion anchors, idempotence, and preservation of project-owned content.
- [x] Retain and exercise invalid, duplicate, missing-file, and symlink failure cases.
- [x] Add or extend a Copier update fixture only as needed to prove customized whitespace survives the supported update path.
- [x] Run required unit, generated-project, and update validation.

## Validation Notes

- The normalizer now recognizes TOML-permitted leading horizontal whitespace on the two fixed model fields and on the name or description insertion anchor, while retaining the original indentation.
- Focused tests cover indented replacement and insertion, idempotence, invalid and duplicate TOML, missing profiles, symlinks, and preservation of project-owned profile content.
- The mature-project Copier fixture proves that customized indented profiles retain unrelated fields and instructions while only the fixed model values are normalized.
- `python3 tests/test-agent-model-profiles.py`, `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `COPIER_UPDATE_TARGET_REF=437b950 REQUIRE_COPIER=1 tests/copier-update.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed.
