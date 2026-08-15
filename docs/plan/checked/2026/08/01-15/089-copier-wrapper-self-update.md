# Keep the Copier update wrapper stable while it replaces itself

status: checked
primary_invariant: a clean supported update must complete even when Copier replaces the running update wrapper
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/scripts/update-from-copier.sh
  - template/.project-agent-workflow/scripts/run-copier-update.sh
  - tests/copier-update.sh
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/088-copier-update-safety-contract.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/check-copier-template.py
validation:
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Reproduce a v1.4.1-to-current update by invoking the generated wrapper itself and require the wrapper process to exit successfully.
  - Keep force-flag rejection, clean-worktree preflight, Copier trust, and final ownership validation unchanged.
  - Prevent replacement of the on-disk wrapper from changing the commands still to be executed by the current shell process.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 実行中に自身が更新される Copier ラッパーを、処理の途中で読み替えない構造に修正した。

## Decisions

- Keep the v1.4.1 wrapper's byte offset through its Copier invocation stable, and dispatch future updates through a managed helper.
- Replace the current wrapper process with the managed helper, and parse the helper's complete update sequence, including final validation, before invoking Copier.
- Keep both entrypoints at generated paths and avoid introducing temporary executable copies.
- Add a real Copier regression fixture that starts from v1.4.1, where the wrapper bytes differ from the current template.
- Add a second update that changes the helper bytes, proving that the current helper completes after replacing itself.

## Tasks

- [x] Add the self-replacing wrapper regression fixture.
- [x] Make both the legacy wrapper return path and the generated helper execution independent of later on-disk replacement.
- [x] Run focused validation, independent review, and authoritative validation.
- [x] Archive and commit the accepted change.

## Validation Notes

- A disposable gakumasu-timeline clone updated its managed files to `6ef4400`, then the v1.4.1 wrapper resumed at a shifted byte offset and failed with `.project-agent-workflow/scripts/update-from-copier.sh: 24: update: not found`.
- Focused validation proved that changing only the new wrapper is insufficient: the v1.4.1 process has already parsed the old Copier command and resumes at its old byte offset after the file is replaced.
- The final wrapper keeps the v1.4.1 post-Copier resume command at byte offset 466, dispatches future updates through a managed helper, and terminates the already-parsed helper command list after Copier returns.
- `REQUIRE_COPIER=1 tests/copier-update.sh`: passed, including both v1.4.1 wrapper replacement and a subsequent helper-byte-shift update.
- Independent read-only review reported zero High, Medium, or Low findings after remediation.
- `python3 scripts/check-copier-template.py`: passed.
- `TMPDIR=/var/tmp scripts/lint-project-workflow.sh`: passed.
- `TMPDIR=/var/tmp REQUIRE_COPIER=1 tests/smoke.sh`: passed; actionlint was unavailable and its existing optional checks were skipped.
- `python3 scripts/validate-changes.py --all`: passed.
- `git diff --check`: passed. No unresolved risk or deferred work remains.
