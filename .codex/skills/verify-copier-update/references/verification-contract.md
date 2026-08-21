# Verification Contract

## Required inputs

- `--target` names a clean downstream Git repository root.
- `--source` names a clean Copier template Git repository root.
- `--source-ref` names an existing source commit, branch, or tag and is resolved to one commit OID before cloning.
- `--output-dir` names a new path outside both repositories and holds the disposable workspace, logs, and manifest.
- `--trust-template-tasks` records the caller's authorization to run the reviewed local template tasks with Copier `--trust`.
- Each `--validation-command-json` value is one nonempty JSON array of strings executed directly without a shell.
- `--copier-command-json` may select a reviewed local Copier launcher such as `["uv", "run", "copier"]`; it defaults to `["copier"]`.

The Copier launcher accepts only `copier` or `uv run copier` without extra arguments; the helper supplies all update flags itself.

Do not use a moving word such as `latest` as evidence.

Record the resolved commit OIDs even when the selector is a stable tag.

## Isolation and update path

The helper requires both original worktrees to be clean Git roots and rejects symbolic-link roots.

It clones without hard links, checks out the exact downstream and source commits, and recreates the downstream answer file's relative `_src_path` relationship inside one same-filesystem workspace.

Absolute, missing, ambiguous, or workspace-escaping `_src_path` values stop as `blocked` rather than being rewritten.

The helper uses `.project-agent-workflow/scripts/update-from-copier.sh` when the baseline provides it.

Without that wrapper, it permits direct trusted `copier update` only for a v1-or-newer baseline that already has `.project-agent-workflow/`.

Pre-v1 adoption remains a separate migration workflow.

Child commands receive a bounded environment with a private `HOME`, temporary directory, locale, `PATH`, and `CI=1`; credentials and arbitrary environment values are not forwarded.

This reduces credential exposure but does not prove operating-system network isolation.

Inspect template tasks and downstream validation commands before authorizing execution.

Before any original-repository status inspection, the helper rejects Git submodules and effective repository-local external clean or process filters. After confirming clean Git-visible status, it also rejects nondefault `assume-unchanged` or `skip-worktree` index flags. These states would make a non-mutating raw worktree comparison ambiguous or allow inspection to execute repository code.

## Required checks

After the update command succeeds, the helper requires the updated generated validator and runs it explicitly.

It records the update `HEAD` and Git-visible status, runs `git diff --check`, the updated generated `validate-changes.py --all`, and every target-specific validation argv, then requires the recorded `HEAD` and status to remain unchanged.

It reruns the generated update validator and whitespace check after target-specific validation before creating the disposable commit.

It records the changed paths, commits only inside the disposable clone, repeats the same update, reruns the generated validator and whitespace check, and requires a clean second result.

The helper disables optional Git lock refreshes and system or global Git configuration while inspecting the originals. It snapshots symbolic and resolved `HEAD`, refs and symbolic ref targets, raw index and split-index bytes, raw tracked regular-file or symbolic-link state and actual modes, clean status, and bounded ignored-file identity. It captures tracked raw state both before and after Git status inspection to detect observer effects, then compares both repositories again after every success or failure path.

## Results and evidence

- `verified` means every required check and the same-ref idempotence check passed for the recorded commit OIDs.
- `rejected` means an update or required invariant check completed with an observed failure.
- `blocked` means a prerequisite prevented the required checks from completing, so compatibility remains unresolved.

`verification-manifest.json` contains schema version, result, bounded reason code and detail, exact Git identities, selected update path, changed paths, command exit status and log digests, and unresolved facts.

It does not contain credentials, raw environment values, original absolute repository paths, or full command arguments.

Full stdout and stderr remain in separate local log files under the output directory and must not be committed.
