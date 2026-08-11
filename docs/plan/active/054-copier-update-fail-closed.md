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
  - The overlap fixture modifies the same existing line to two different values and invokes `copier update --defaults --trust` without `--force`/`-f`, matching the documented update semantics rather than suppressing the conflict.
  - The update test refuses any fixture repository that resolves outside its temporary directory or resolves to the source repository.
  - The source repository HEAD and worktree remain unchanged across the update test.
  - Git inspection failures make the post-update validator exit nonzero instead of being interpreted as an empty clean result.
  - The mutable-source update fixture copies from one explicit semantic-version tag and updates to a later explicit semantic-version tag.
  - The listed host-side validation command works without sandbox-only environment variables; the test prefers `SANDBOXED_PLAN_WORKER_SCRATCH_DIR` when present and otherwise creates its disposable tree below `TMPDIR` without writing into the repository.
  - Result scanning does not follow symbolic links outside the destination, and Git's explicit non-repository diagnosis is evaluated under a deterministic C locale.
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
- Build the conflict lane by replacing the same baseline managed-file line in the project and the later template tag with distinct values; invoke the update noninteractively with `--defaults` but never force it.
- Separate source-repository reads from fixture writes; every Git command that can mutate state must reject the source repository and any path outside the test temporary directory.
- Use consecutive explicit semantic-version tags for the mutable-source copy and update instead of `HEAD` provenance.
- Treat Git inspection errors as validator failures, except for the explicit non-Git destination check used by initial copies.
- Recognize only Git's explicit not-a-repository result as the initial-copy exception; any other nonzero Git result, including an injected inspection failure, is fatal.
- Classify only `.github/workflows/codex-ci-autofix.yml` and `scripts/skillspector-scan.sh` as expected update deletions; do not allow deletion by directory prefix.
- Guard every fixture Git mutation at the command boundary: resolved `-C` repositories and clone destinations must remain below the test temporary directory and must never equal the source repository.
- Store transient validation and diagnostic logs only under `SANDBOXED_PLAN_WORKER_SCRATCH_DIR`; do not leave root-level log files or other diagnostic artifacts in the candidate repository.
- When the sandbox scratch variable is absent during normal host validation, use `TMPDIR` (or the system temporary directory) as the disposable fixture parent; never require a sandbox-only variable in the documented validation command.
- Skip symbolic links while scanning result files for conflict blocks and force `LC_ALL=C` for validator Git subprocesses before classifying the explicit non-repository result.

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
- Rejected sandbox run from source `c6f1c91`: it became unresponsive after validation and left root-level `copier-update*.log` diagnostics outside `write_scope`; the run was interrupted and its temporary clone was removed without a manifest or source mutation.
- Rejected physically scoped candidate `af3cca8ad993e15e8ad9cec46da1b5c9f1620f77f4a6366969768446d33173bb` after independent review: the exact listed command `REQUIRE_COPIER=1 tests/copier-update.sh` exited 2 because it unconditionally required `SANDBOXED_PLAN_WORKER_SCRATCH_DIR`, so it passed only inside the delegated runner. Its validator also followed file symlinks during conflict scanning and classified Git stderr without fixing the locale. Preserve the fail-closed Git/deletion implementation and fixture guards, add the safe host temporary fallback and non-following scan, and rerun every listed command outside the worker environment in the review clone.
- Rejected physically scoped candidate `f03686488d39e25107c9082e85f788c6f171941ef33a4afcf5f9c2d4aadf7953` after the exact host-side `REQUIRE_COPIER=1 tests/copier-update.sh` reached the conflict lane and failed with `overlapping managed-file update unexpectedly succeeded`. The fixture appended different lines, which merged cleanly, and invoked update with `-f`, unlike the documented command. Preserve the portable scratch fallback, non-following scan, locale, exact deletion allowlist, and Git guards; change both sides of one existing managed line to distinct values and run `update --defaults --trust` without force.
