# Release Workflow

This runbook covers one release of this template repository, from resolving the request to reporting the outcome. Follow the steps in order. Stop at the step where the request ends: a preparation request ends at step 5.

## 1. Resolve The Request

Establish these before writing anything, from live repository state:

- the requested phase: preparation only, publication of already-prepared content, or both;
- the previous stable tag (`git tag -l 'v*' --sort=-v:refname | head -1`) and its target commit;
- the candidate commit to release, and whether the working tree is clean;
- the intended version;
- the source ref the work is developed on, the integration ref a pull request would target, and the ref a tag would be created at;
- whether a pull request was requested, and whether a GitHub Release object was requested.

Do not copy `dev`, `main`, or a version number from a past release plan. Past plans record what those refs were at the time; read the current ones.

If the request is preparation only, say so explicitly in the final report and stop after step 5. A preparation report states what was changed locally and what remains unauthorized, and claims nothing about remote state.

## 2. Choose The Version

Use the criteria in `README.md`. In short: a major version for a change that forces manual migration in an existing generated project, a minor version for a backward-compatible addition to `copier.yml`, `template/`, or generated operating rules, and a patch version for a correction that adds no capability.

Inspect the actual change set rather than the commit subjects:

```sh
git diff <previous-tag>..<candidate> -- copier.yml template scripts tests docs references README.md
```

Also inspect `copier.yml` for migration steps whose version conditions constrain which versions a downstream project may cross. A migration bounded to a version range is a fact about the release, not a detail.

The `version` field in `pyproject.toml` is a packaging placeholder. It is not the Copier release version and is not part of this decision.

When the history and the current criteria do not point at one version — for example a correction that also changes a generated contract — present the concrete impact on generated projects and let the owner decide. Do not invent a versioning rule to break the tie.

## 3. Prepare In A Task Worktree

Create the bound checkout before changing anything:

```sh
python3 scripts/manage-plan-worktrees.py prepare <plan-path>
python3 scripts/manage-plan-worktrees.py prepare --direct-task <task-id>
```

Review what is being released:

```sh
git diff <previous-tag>..<candidate> --stat
```

Then, in the worktree:

- date the accumulated `未リリース` section in `CHANGELOG.md` as the new release heading and leave an empty `未リリース` section above it, because the version check requires that marker;
- update only the current stable-version anchors in `README.md`, leaving external link targets untouched;
- preserve unrelated product changes and every historical plan record; a release never edits archived plans, contracts, or change-log entries of earlier versions.

Confirm agreement with the check that owns it rather than by reading:

```sh
python3 scripts/check-copier-template.py
```

A release also follows the normal plan workflow: classify the tier, carry the plan through `scripts/complete-plan.sh` and `scripts/finalize-active-plan.sh`, and commit inside the worktree.

## 4. Validate The Candidate

Run the repository's own validation, following `references/template-development.md` and `.github/workflows/ci.yml`:

- `UV_CACHE_DIR=.uv-cache uv sync` when dependencies are not yet present;
- `python3 scripts/check-copier-template.py`;
- `scripts/lint-project-workflow.sh`;
- `tests/smoke.sh`;
- `tests/test-hooks.py`;
- `tests/copier-update.sh`, including the direct-update guard and the recopy-based pre-v1 adoption lanes;
- the Copier copy and update paths against a generated sample when the Copier CLI is available;
- `git diff --check` as the whitespace gate;
- the current minimum-compatibility and `actionlint` checks.

The Copier and workflow checks are release-relevant: a template release that never exercised a generated project has not been tested on the thing it ships. If a check cannot run — no Copier CLI, no network, no `uv` — name it as skipped in the report instead of treating the suite as complete.

Record which commit each result belongs to. A result may be reused only when both the tested input and the command are unchanged. Success on a pull-request head does not carry over to the merge commit or to the tag commit, because those are different trees or different parents.

## 5. Verify Downstream Baselines

Run the downstream verification for the exact candidate source OID and every configured baseline in `docs/downstream-baselines.yaml`, writing evidence outside the repository as the command requires:

```sh
python3 scripts/verify-downstream-baselines.py --source-commit <oid> --output <external-dir>
```

Read the result and the reason for each baseline separately:

- `target_dirty`, or any other blocked result, stops tagging until the owner resolves it;
- `verified` proves only the checks the run actually recorded, which does not include that project's own product tests.

Never clean or modify a downstream checkout to obtain a result, never invent a product command for a baseline, never drop a configured baseline, and never infer a waiver from what plans 290 or 329 once accepted.

Preparation ends here. Everything below is publication.

## 6. Finish The Task Locally

Publish the task worktree before any remote operation, so the accepted commit reaches the source branch and the temporary branch and checkout are gone:

```sh
python3 scripts/manage-plan-worktrees.py publish <plan-path>
python3 scripts/manage-plan-worktrees.py publish --direct-task <task-id>
```

## 7. Authorize Each External Effect

Apply `docs/agent/SPEC_EXTERNAL_SERVICES.md` and the `mcp-ops` guidance to each effect separately:

- pushing the source branch;
- creating or updating a pull request;
- pushing a tag;
- publishing a GitHub Release.

Reuse an existing user authorization only when it already names that exact effect and target. Ask for a missing authorization only after the target and payload are concrete enough to review; an authorization request that does not name what will be written is not reviewable.

Use exact refs rather than bulk pushes, so the effect matches what was authorized:

```sh
git push origin refs/heads/<source-branch>
git push origin refs/tags/<tag>
```

## 8. Integrate

For a requested pull-request path, open the pull request with the exact head and base and a body that describes the release, then wait for the required merge. Do not introduce an automatic merge step: the merge is the owner's or the platform's action, and the release does not assume it happened.

After the merge, establish the exact remote OID of the publication branch and confirm it contains the preparation commit. That OID, not the local branch tip, is what a tag points at.

## 9. Tag

Before creating the tag, inspect whether it already exists, locally and remotely:

```sh
git tag -l <tag>
git ls-remote --tags origin refs/tags/<tag>
```

An existing tag at the intended target is evidence that a previous attempt got this far. Resume from it; do not recreate it. An existing tag at a different target stops the operation and goes to the owner. Never force-move and never delete a published tag.

Otherwise create an annotated tag at the verified publication OID and confirm what it dereferences to:

```sh
git tag -a <tag> -m "Release <tag>" <publication-oid>
git rev-parse <tag>^{commit}
```

## 10. Inspect Post-Tag CI

Tag-context CI runs against a commit and an environment that preparation did not necessarily exercise. Plan 092 records exactly this: preparation succeeded and the tag context still failed.

Inspect the CI outcome for the exact tag commit before publishing a GitHub Release. If it fails:

- keep the published tag; deleting it destroys the evidence and breaks anyone who already resolved it;
- withhold both the success claim and the Release publication;
- route diagnosis and correction through current repository policy.

Do not quietly move to another version number to escape a failure.

## 11. Recover From An Interrupted Release

When a previous attempt's outcome is uncertain, read state before writing:

- `git ls-remote origin` for the exact branch and tag refs;
- the pull request and merge state;
- the CI runs for the relevant commits;
- whether a GitHub Release object exists for the tag.

An operation whose recorded effect already matches the intended one is complete; reuse it. A mismatch stops the retry and goes to the owner. Retrying an uncertain write without reading first is how a release acquires a second tag or a duplicated Release.

## 12. Report

Report these as separate facts, and do not merge them into one success claim:

- the preparation commit;
- the publication branch OID;
- the tag and the commit it dereferences to;
- the CI outcome for that commit, and any check that was skipped or unavailable;
- the downstream verification result per baseline, including what it does not prove;
- the GitHub Release URL, or an explicit statement that no Release was published and why.
