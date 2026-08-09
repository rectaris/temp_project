# Validate v1.1.2 across four projects

status: checked
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
write_scope:
  - README.md
  - docs/plan/
  - scripts/
  - template/
  - tests/
context_files:
  - ../curiretas-account/
  - ../curiretas-gakumas-portal/
  - ../gakumasu-timeline/
  - ../supportcard-status/
  - .agent-artifacts/referent-contracts/v112-four-project-adoption/contract.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/copier-minimum.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Preserve this condition: each source repository remains unchanged while its current commit is copied to an isolated temporary clone for the candidate operation.
  - Select the supported transition this way: the command under test is selected from the committed _commit value and current generated layout: pre-v1 or v1.0.0 uses adopt-to-namespaced-layout.py, while v1.1.0 or newer uses copier update.
  - Require this evidence: a project is applicable only when the candidate operation leaves no unmerged paths or unexpected tracked-file deletions, preserves project-owned files and Hook wiring, passes managed template validation, and passes repository-required validation.
  - Preserve this ownership boundary: only a failure common to generated workflow behavior is repaired in temp_project; project-specific application behavior remains in its owning repository and is reported without importing it into the template.
checked_summary_ja: 4プロジェクトを一時 clone で v1.1.2 候補へ更新し、Copier の適用経路、差分、Hook、テンプレート検証、各プロジェクトの検証結果を確認した。

## Decisions

- Confine Copier writes, dependency environments, and test artifacts to isolated temporary directories.
- Resolve the local v1.1.2 candidate tag to the current temp_project commit without creating or rewriting a tag in the source repository.
- Require repository-specific instructions and validation in addition to managed template checks.
- Add a temp_project regression test before repairing any common generated-workflow defect.
- Do not render plan-directory `.gitkeep` placeholders because Copier recreates a deleted skipped placeholder during later updates.
- Preserve pre-v1 open and checked plans byte-for-byte. Validate checked history structurally without applying current command or policy routes retroactively, and accept an open plan's legacy command only when a v0 adoption manifest and an exact executable compatibility bridge prove its origin.
- Replace only byte-identical, standalone pre-v1 generated CLI entrypoints with executable bridges to the managed implementation. Preserve and report modified, symlinked, importable, or unverifiable scripts.

## Tasks

- [x] Inspect the current Copier answers and repository instructions for all four projects.
- [x] Run the supported v1.1.2 candidate operation in four independent temporary clones.
- [x] Inspect conflicts, tracked-file deletions, preserved project files, Hook wiring, and generated workflow validation.
- [x] Run each project's required application validation and classify any failure by ownership.
- [x] Repair and reproduce any common template defect.
- [x] Run temp_project completion validation and archive this plan.

## Validation Notes

- Candidate commit `a4704d25ba4dbd267346a79b90e31cca5a84417a` was copied to an isolated source clone and tagged locally as `v1.1.2` for every project preflight. No source project was modified.
- `curiretas-account` passed the v0.5.0 adoption path, preserved active and checked plan digests, bridged 25 byte-identical legacy CLI entrypoints, passed both root and managed validation, and passed `npm run verify` with 20 tests. Its application commit should route the preserved authentication policy from `docs/agent/PROJECT_POLICY.md` before retiring the old root routing entry.
- `curiretas-gakumas-portal` passed the v1.1.1 ordinary update path, managed validation, six application tests, type checking, and build. It requires no project-specific integration change.
- `gakumasu-timeline` passed the v1.0.0 adoption path, managed validation, 144 application tests, seven Worker tests, data and UI checks, and build. It requires no project-specific integration change.
- `supportcard-status` passed the v1.1.1 ordinary update path after its project-owned source-version documentation and validation assertions were changed to `v1.1.2` in the isolated clone. Managed and root validation, 351 frontend tests, 276 Python tests, lint, and build passed. Its historical migration manifest remains at its original v1.1.1 adoption value.
- Every candidate operation left no unmerged paths, unexpected tracked-file deletion, or rejection files; preserved project-owned files and Hook wiring; refused compression of namespaced policy; and produced no diff on a second same-version update.
- Generic defects repaired: removed four plan-directory placeholders that Copier recreated after project deletion; added provenance-bound compatibility for pre-v1 plan validation; and added digest-checked executable bridges for unchanged pre-v1 root CLI entrypoints.
- Independent subagents reviewed each project path and the plan-compatibility and bridge boundaries. The implementation review found no remaining blocking issue.
- Completion validation passed: `scripts/lint-project-workflow.sh`, `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 COPIER_SMOKE_REF=a4704d25ba4dbd267346a79b90e31cca5a84417a tests/smoke.sh`, `COPIER_UPDATE_TARGET_REF=a4704d25ba4dbd267346a79b90e31cca5a84417a REQUIRE_COPIER=1 tests/copier-update.sh`, `COPIER_MINIMUM_REF=a4704d25ba4dbd267346a79b90e31cca5a84417a tests/copier-minimum.sh`, `tests/root-plan-lifecycle.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check`.
