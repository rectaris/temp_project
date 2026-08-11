# Make the documented Copier update path fail closed

status: in_progress
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
  - tests/copier-update.sh
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
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The documented `copier update --trust` path exits nonzero when unresolved index conflicts, rejection files, complete inline conflict blocks, or unclassified tracked-file deletions remain.
  - A clean initial copy remains supported outside a Git repository.
  - A conflict-free update continues to preserve project-owned files and validation behavior.
  - An intentionally overlapping managed-file update fixture proves the failure is surfaced by the supported command itself.
  - The update test refuses any fixture repository that resolves outside its temporary directory or resolves to the source repository.
  - The source repository HEAD and worktree remain unchanged across the update test.
  - Git inspection failures make the post-update validator exit nonzero instead of being interpreted as an empty clean result.
  - The mutable-source update fixture copies from one explicit semantic-version tag and updates to a later explicit semantic-version tag.
checked_summary_ja: 文書化された Copier update 経路を競合、rej、未分類削除で失敗させ、成功終了のまま不整合を残さない。

## Context

The documented Copier update path must exit nonzero when conflicts, rejection files, or unclassified deletions remain.

Copier can return success while leaving an unresolved Git conflict, but the generated documentation currently directs users to the raw command without a deterministic post-update gate.

## Decisions

- Keep Copier and `copier.yml` as the long-term interface.
- Run the result gate as part of the trusted Copier task sequence rather than relying on a separate optional manual command.
- Detect complete conflict blocks so valid Markdown setext headings are not rejected.
- Resolve every mutable fixture path before Git writes, require it to be below the test temporary directory, and reject the source repository explicitly.
- Snapshot the source repository HEAD and worktree before the test and require both to remain unchanged afterward.
- Keep the update source's Copier provenance valid so the supported update command can detect its previous version.
- Separate source-repository reads from fixture writes; every Git command that can mutate state must reject the source repository and any path outside the test temporary directory.
- Use consecutive explicit semantic-version tags for the mutable-source copy and update instead of `HEAD` provenance.
- Treat Git inspection errors as validator failures, except for the explicit non-Git destination check used by initial copies.
- Recognize only Git's explicit not-a-repository result as the initial-copy exception; any other nonzero Git result, including an injected inspection failure, is fatal.
- Classify only `.github/workflows/codex-ci-autofix.yml` and `scripts/skillspector-scan.sh` as expected update deletions; do not allow deletion by directory prefix.
- Guard every fixture Git mutation at the command boundary: resolved `-C` repositories and clone destinations must remain below the test temporary directory and must never equal the source repository.

## Tasks

- [ ] Add a post-copy/update result validator that is safe for initial non-Git copies.
- [ ] Wire the validator into the trusted Copier task sequence.
- [ ] Add a conflict-producing update fixture and retain the conflict-free update lane.
- [ ] Add fail-closed fixture-path guards and a source-repository immutability assertion.
- [ ] Add an injected Git inspection-failure fixture and explicit deletion-classification coverage.
- [ ] Align generated update documentation with the enforced behavior.
- [ ] Run the required validation commands.

## Validation Notes

- Rejected sandbox candidate `fe2670d159f5f2ff39133e13a066144085ecc83c41c4f1d0c93bfa208ddd6ecf`: it treated every initial Git probe failure as non-Git, allowed broad deletion prefixes, and did not guard each fixture Git mutation target.
