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
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The generated and documented `.project-agent-workflow/scripts/update-from-copier.sh` path exits nonzero when Copier fails or unresolved index conflicts, rejection files, complete inline conflict blocks, or unclassified tracked-file deletions remain.
  - The one-time v1.2.2 `after` migration validates the final merge result so an existing v1.2.1 project cannot cross the wrapper-installation boundary with unresolved state while raw Copier reports success.
  - A clean initial copy remains supported outside a Git repository.
  - A conflict-free update continues to preserve project-owned files and validation behavior.
  - Intentionally overlapping managed-file fixtures prove both the v1.2.1-to-v1.2.2 migration boundary and the generated wrapper surface the failure through their supported command.
  - The overlap fixtures modify the same existing line to two different values and never use `--force`/`-f`.
  - The generated wrapper rejects `--force` and `-f` before invoking Copier.
  - The generated wrapper resolves its owning repository root and changes to it before invoking Copier, so invocation from another working directory cannot update or inspect the caller's repository.
  - Repository root resolution is exactly two parent levels above `.project-agent-workflow/scripts/update-from-copier.sh` (`../..` from the script directory), and static/focused checks reject an extra parent traversal.
  - The v1.2.2 boundary fixture invokes raw `copier update --defaults --trust` because the v1.2.1 project cannot contain the wrapper yet; a separate clean transition installs the wrapper before a later tagged conflict exercises the recurring path.
  - Deletion checks cover both staged and unstaged tracked deletions by comparing the worktree and index to `HEAD`, and filesystem result scanning catches ignored `*.rej` files without following symbolic links.
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

Copier 9.15.1 executes ordinary `_tasks` while rendering temporary old/new copies during update. Only an `after` migration runs after the final smart-merge result, and a versioned migration runs only when crossing its version boundary. Therefore an ordinary task cannot enforce recurring post-update validation.

## Decisions

- Keep Copier and `copier.yml` as the long-term interface.
- Do not wire final-result validation through ordinary `_tasks`; that lifecycle cannot observe the final update merge.
- Add a v1.2.2 `after` migration that validates the first update which installs the recurring wrapper.
- Generate `.project-agent-workflow/scripts/update-from-copier.sh` as the documented recurring update command. It runs Copier without force and then runs the generated validator against the repository root.
- Prove first installation with two lanes: raw v1.2.1-to-v1.2.2 conflict is stopped by the after migration, while a clean raw transition installs the wrapper before a later explicit tag is tested through that wrapper.
- Keep the source and generated validator implementations byte-identical and cover their parity deterministically.
- Enforce source/template validator byte parity in the static template check as well as the generated-project fixture.
- Detect complete conflict blocks so valid Markdown setext headings are not rejected.
- Resolve every mutable fixture path before Git writes, require it to be below the test temporary directory, and reject the source repository explicitly.
- Snapshot the source repository HEAD and worktree before the test and require both to remain unchanged afterward.
- Keep the update source's Copier provenance valid so the supported update command can detect its previous version.
- Build the conflict lane by replacing the same baseline managed-file line in the project and the later template tag with distinct values; invoke the update noninteractively with `--defaults` but never force it.
- Separate source-repository reads from fixture writes; every Git command that can mutate state must reject the source repository and any path outside the test temporary directory.
- Use consecutive explicit semantic-version tags for the mutable-source copy and update instead of `HEAD` provenance.
- Compare deletions to `HEAD` so staged and unstaged removals are both visible, and walk non-symlink filesystem entries outside `.git` so ignored rejection files remain blockers.
- Treat Git inspection errors as validator failures, except for the explicit non-Git destination check used by initial copies.
- Recognize only Git return code 128 plus its C-locale explicit not-a-repository diagnosis as the initial-copy exception; any other nonzero Git result, including the same text with a different return code or an injected inspection failure, is fatal.
- Classify only `.github/workflows/codex-ci-autofix.yml` and `scripts/skillspector-scan.sh` as expected update deletions; do not allow deletion by directory prefix.
- Guard every fixture Git mutation at the command boundary: resolved `-C` repositories and clone destinations must remain below the test temporary directory and must never equal the source repository.
- Store transient validation and diagnostic logs only under `SANDBOXED_PLAN_WORKER_SCRATCH_DIR`; do not leave root-level log files or other diagnostic artifacts in the candidate repository.
- When the sandbox scratch variable is absent during normal host validation, use `TMPDIR` (or the system temporary directory) as the disposable fixture parent; never require a sandbox-only variable in the documented validation command.
- Skip symbolic links while scanning result files for conflict blocks and force `LC_ALL=C` for validator Git subprocesses before classifying the explicit non-repository result.
- When constructing a mutable template source from an uncommitted candidate, copy every new source/template script explicitly as well as applying tracked diffs before committing the fixture tag; do not assume `git diff` carries untracked files.
- Replace the pre-existing future-source `HEAD` copy/update lane with consecutive explicit test tags too; the semantic-tag rule applies to every mutable-source lane, not only the new gate fixtures.

## Tasks

- [ ] Add a post-copy/update result validator that is safe for initial non-Git copies.
- [ ] Wire the validator into the v1.2.2 after migration and add the generated recurring update wrapper.
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
- Rejected physically scoped candidate `b6e0ba02f98c2a5512d3a8126b03f0d68fd1ae9de3b0cf3709486529b220ceab` after the corrected same-line/non-force fixture still failed with `overlapping managed-file update unexpectedly succeeded` in the exact host-side suite. Copier 9.15.1 source confirms ordinary tasks run in temporary `run_copy()` render phases, while only post-migration tasks run after the smart merge. Replace the ineffective ordinary-task design with a v1.2.2 after-migration gate for first installation plus a generated recurring wrapper. Also restore the explicit return-code-128 condition and use explicit semantic-version tags in every mutable-source update lane.
- Rejected physically scoped candidate `79d06883f7ef9840e6668935898892edb308db0b13500454f860f5de85f0549b` during main-session code review before host validation: its v1.2.1 boundary fixture called the not-yet-installed wrapper, its validator used `git diff` without `HEAD` and could miss staged deletion, its Git-visible-only conflict scan could miss ignored `*.rej`, and the existing future-source lane still used `HEAD` provenance. Split raw boundary and installed-wrapper fixtures, compare deletion against `HEAD`, add an ignored-rejection fixture, and give every mutable-source lane explicit consecutive semantic-version tags.
- Rejected physically scoped candidate `2e4418fe03c0669895b8fda4229999cc1629a54ad9793e6d4188bbdd1f0dd99d` during main-session fixture review before host validation: its update-source clone applied only `git diff --binary HEAD`, which omits the new validator and wrapper files, and its older future-source lane still copied and updated from `HEAD`. Preserve the accepted after-migration, wrapper, source/template validator parity, staged/unstaged deletion, ignored rejection, and split bootstrap/recurring fixture design; explicitly copy new candidate files into the source commit and tag every mutable-source before/after revision.
- Rejected physically scoped candidate `55ea9c3d82d96c061426e1a3e72d5c74cf116c26e4d76edb49276561f3252861` during main-session wrapper review before host validation: the wrapper resolved its repository root but did not `cd` there before running `copier update`, so an absolute-path invocation from another cwd could operate on the caller instead. Preserve its global fixture Git guard, explicit tags, candidate-file copy, validator behavior, and split gate fixtures; change to the resolved root before both commands, exercise the wrapper from an outside cwd, and add direct static source/template validator parity enforcement.
- Rejected physically scoped candidate `3c4c5d9ff0a5b9da8509457acdfd3c8b4aa173e1bc9263d5b3e8b7144f2b22b0` during main-session wrapper review before host validation: it changed cwd but resolved `../../..` from `.project-agent-workflow/scripts`, landing at the repository's parent rather than the repository root. Preserve the static validator parity and accepted gate design; use exactly `../..`, assert that literal in the static check, and prove a clean wrapper update succeeds when invoked by absolute path from the fixture parent.
