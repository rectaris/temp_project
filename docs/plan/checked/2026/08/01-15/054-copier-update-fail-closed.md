# Make the documented Copier update path fail closed

status: checked
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - copier.yml
  - docs/plan/active/054-copier-update-fail-closed.md
  - scripts/
  - template/README.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/.project-agent-workflow/scripts/
  - tests/copier-update.sh
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - references/template-development.md
  - tests/lib-copier.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - env -u SANDBOXED_PLAN_WORKER_SCRATCH_DIR REQUIRE_COPIER=1 tests/copier-update.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The v1.2.2 `after` migration rejects an unresolved final merge during the first wrapper-installing update.
  - The generated and documented `.project-agent-workflow/scripts/update-from-copier.sh` rejects force flags, changes to its owning repository root using exactly `../..`, runs Copier, and rejects an unsafe final result.
  - The post-update validator rejects Git inspection failure, index conflicts, ignored `*.rej`, complete inline conflict blocks, and tracked deletions outside the two exact allowlisted paths.
  - A clean non-Git initial copy, a clean v1.2.1-to-v1.2.2 transition, and a later conflict-free wrapper update remain supported.
  - Source and generated validators are byte-identical and their parity is checked statically.
  - Integration fixtures use explicit consecutive semantic-version tags, create a real same-line conflict without force, and separately cover the first migration boundary and recurring wrapper path.
  - Every fixture Git mutation is confined below its resolved temporary root, and the source repository HEAD and worktree remain unchanged.
  - Filesystem scanning skips symbolic links, uses deterministic C-locale Git diagnostics, and catches ignored result files.
  - The full Copier suite passes both with sandbox scratch available and with that variable explicitly unset.
checked_summary_ja: 文書化された Copier update 経路を競合、rej、未分類削除で失敗させ、成功終了のまま不整合を残さない。

## Context

The documented Copier update path must exit nonzero when conflicts, rejection files, or unclassified deletions remain.

Copier can return success while leaving an unresolved Git conflict, but the generated documentation currently directs users to the raw command without a deterministic post-update gate.

Copier 9.15.1 executes ordinary `_tasks` while rendering temporary old/new copies during update. Only an `after` migration runs after the final smart-merge result, and a versioned migration runs only when crossing its version boundary. Therefore an ordinary task cannot enforce recurring post-update validation.

## Decisions

- Keep Copier and `copier.yml` as the long-term interface.
- Use only a v1.2.2 `after` migration for the first final-merge gate; ordinary `_tasks` cannot observe Copier's final smart merge.
- Use a generated wrapper for every later supported update and document that wrapper instead of raw recurring updates.
- Keep one validator implementation copied byte-for-byte to the generated path.
- Treat only Git return code 128 with the C-locale explicit non-repository diagnosis as the clean initial-copy exception.
- Compare tracked deletions with `HEAD`; allow deletion only for `.github/workflows/codex-ci-autofix.yml` and `scripts/skillspector-scan.sh`.
- Scan non-symlink filesystem entries outside `.git` for rejection files and complete conflict blocks.
- Use two integration lanes: a raw v1.2.1-to-v1.2.2 boundary lane and a clean installation followed by a later wrapper lane.
- Build mutable template sources from explicit tags and explicitly copy candidate-created files before committing fixture tags.
- Guard all fixture Git mutations at their command boundary and store transient output only under sandbox scratch or a system temporary directory.

## Implementation Sequence

1. Add focused validator behavior and source/generated parity checks.
2. Add the wrapper with exact `../..` root resolution, outside-cwd coverage, and force-flag rejection.
3. Add the v1.2.2 `after` migration after validator and wrapper paths are stable.
4. Add guarded explicit-tag fixtures for clean bootstrap, migration conflict, clean wrapper update, and wrapper conflict.
5. Run the full Copier suite with sandbox scratch and again with `SANDBOXED_PLAN_WORKER_SCRATCH_DIR` unset before emitting a candidate.

## Tasks

- [x] Implement and focus-test the post-update validator, including parity and initial non-Git behavior.
- [x] Implement and focus-test the recurring wrapper before wiring the migration.
- [x] Wire the v1.2.2 `after` migration and add the split explicit-tag integration lanes.
- [x] Enforce fixture mutation guards, source immutability, deletion classification, ignored rejection, locale, and symlink coverage.
- [x] Align generated update documentation and static template checks with the supported commands.
- [x] Run the required validation commands.

## Validation Notes

- Accepted sandbox candidate `4b6c6464ad65c074b4636c64d56aa4a5948ee25c1d99044424affce14531dd28` after independent review-clone validation.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed in the review clone and source repository.
- `env -u SANDBOXED_PLAN_WORKER_SCRATCH_DIR REQUIRE_COPIER=1 tests/copier-update.sh`: passed in the review clone and source repository.
- `scripts/lint-project-workflow.sh`: passed.
- `tests/smoke.sh`: passed with the fallback backend; `actionlint` was unavailable and skipped by the existing smoke behavior.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed.
- Source/generated validator byte parity and the static template check passed.
- No unresolved risks or deferred work remain for this plan.
