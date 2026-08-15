# Keep the Copier update wrapper stable while it replaces itself

status: in_progress
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
  - template/.project-agent-workflow/scripts/update-from-copier.sh
  - tests/copier-update.sh
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

- Parse the complete update sequence into one POSIX shell function before invoking Copier.
- Keep the wrapper at its generated path and avoid introducing temporary executable copies.
- Add a real Copier regression fixture that starts from v1.4.1, where the wrapper bytes differ from the current template.

## Tasks

- [ ] Add the self-replacing wrapper regression fixture.
- [ ] Make the generated wrapper execution independent of later on-disk replacement.
- [ ] Run focused validation, independent review, and authoritative validation.
- [ ] Archive and commit the accepted change.

## Validation Notes

- A disposable gakumasu-timeline clone updated its managed files to `6ef4400`, then the v1.4.1 wrapper resumed at a shifted byte offset and failed with `.project-agent-workflow/scripts/update-from-copier.sh: 24: update: not found`.
