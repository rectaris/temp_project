# Enforce write_scope inside the isolated clone

status: in_progress
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/active/062-filtered-write-scope-sandbox.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/046-sandboxed-plan-worker.md
  - scripts/run-sandboxed-plan-worker.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - The worker sees the repository at its normal clone path, but the clone root is mounted read-only and only normalized write_scope entries are over-mounted from writable scratch storage.
  - An integration test proves an exact-file scope permits in-place content writes while create, content modification, removal, mode change, and rename attempts outside scope fail during worker execution.
  - A prefix-directory scope permits file creation, modification, and deletion below that prefix and denies sibling writes.
  - Trusted post-worker materialization copies only writable-shadow results into the candidate clone before patch collection and preserves deletion semantics for prefix scopes.
  - Exact-file entries fail closed for unsupported removal or atomic replacement; a plan must grant a directory prefix when those operations are required.
  - Exact-file shadow setup accepts only an existing regular file and rejects directories and symbolic links before Bubblewrap is started; prefix-directory copying preserves contained symbolic links without following them.
  - Shadow setup rejects any symbolic-link component between the clone root and the scoped mount target, including a symbolic-link ancestor of a missing prefix, so trusted preparation and materialization cannot escape the normalized repository path.
  - Scratch remains writable for temporary diagnostics and tool caches, and the default worker prompt directs all transient artifacts to `SANDBOXED_PLAN_WORKER_SCRATCH_DIR`.
  - Worker environment setup assigns each reserved variable once and routes Python bytecode, pip cache, uv cache, and uv project environments under scratch; a focused test asserts those exact paths.
  - Bubblewrap or filtered-shadow setup failure exits nonzero without falling back to a whole-clone writable mount.
  - Root and template runners remain byte-identical and executable.
checked_summary_ja: 隔離クローン全体を読み取り専用にし、write_scope の shadow mount だけを書き込み可能にする。

## Context

Plan 046 protects the source repository and rejects out-of-scope candidate paths, but its temporary clone is writable in full.

Plan 054 workers repeatedly created root-level diagnostic files despite explicit scope instructions. The source repository remained protected, but the behavior demonstrated that candidate admission alone does not physically constrain writes inside the clone.

Plan 054 remains suspended until this plan is implemented, validated, archived, and committed.

## Decisions

- Keep Bubblewrap as the mandatory isolation backend.
- Mount the temporary clone read-only inside the worker namespace.
- Prepare writable shadow content under scratch for normalized write_scope entries and bind those entries over their normal clone paths.
- Copy prefix-directory scope trees and exact-file scope content without hard links.
- Materialize shadow results into the candidate clone only after the worker exits successfully and only for normalized scope entries.
- Preserve exact-file mode and content writes, but fail closed when an exact-file operation requires unlink or atomic rename; use a prefix-directory scope for those operations.
- Keep `.git` and every unlisted clone path read-only during delegated execution.
- Set Python and common tool cache locations to scratch where deterministic validation requires temporary writes.
- Keep candidate patch admission as a second independent check after physical write filtering.
- Do not add a whole-clone writable fallback.
- Collapse redundant exact or nested-prefix entries already covered by a broader prefix before creating mounts.
- Route Python bytecode and `uv` cache/project-environment writes to scratch so required validation does not require an unscoped repository-local `.venv` or `__pycache__`.
- Set `PYTHONDONTWRITEBYTECODE`, `PYTHONPYCACHEPREFIX`, `PIP_CACHE_DIR`, `UV_CACHE_DIR`, and `UV_PROJECT_ENVIRONMENT` explicitly, without duplicate reserved environment assignments.
- Reject an exact write-scope target unless `is_file()` is true and `is_symlink()` is false; add focused directory and symbolic-link rejection tests.
- Before preparing any shadow, walk the scoped target path from the clone root and reject every symbolic-link component; add a focused prefix-through-symlink-ancestor test.

## Tasks

- [ ] Build normalized writable shadows for exact-file and prefix-directory scope entries.
- [ ] Mount the clone read-only and bind only shadow entries writable in the worker Bubblewrap command.
- [ ] Materialize shadow results into the candidate clone before sandboxed patch collection.
- [ ] Add physical denial tests for content, creation, deletion, rename, and mode changes outside scope.
- [ ] Add exact-file and prefix-directory behavior tests plus cleanup and parity coverage.
- [ ] Align root and generated orchestration instructions with the stronger boundary.
- [ ] Run every required validation command.

## Validation Notes

- Rejected sandbox candidate `bf9846e9f33843084bcc3173ef7261d39416a89ac9c2b15738e2f8ebdeee5ffa`: the default prompt contained an invalid f-string expansion, the source/outside denial test had dirty-source and inverted postconditions, clone-sibling denial coverage was incomplete, scratch cache routing was incomplete, and overlapping scope entries were not collapsed.
- Rejected sandbox candidate `c8c7caf34ff17c788b1ee72bde1f7b83269b59583c297b301da85eca5277b16c`: 13 of 25 host-side focused tests failed. Writable shadows were mounted before scratch and therefore inherited a read-only source mount; patch collection could not write Git objects with the clone read-only; denial fixtures confused worker-time physical rejection with post-worker admission errors or dirty-source rejection; prefix shadow copying dereferenced symlinks; `UV_PROJECT_ENVIRONMENT` and the default scratch-artifact prompt remained incomplete.
- The next candidate must bind scratch before shadow mounts, keep patch collection separately contained with the candidate clone writable or use a scratch Git object store, preserve symlinks without following them, and prove denial by catching the worker-side `OSError`, completing an allowed write, and emitting a manifest containing only allowed paths.
- Rejected sandbox candidate `716e6314f678a070386025e7e2b9bc105de23211d1e915a42512cd17289b954f`: 13 of 24 host-side tests failed. Scratch-before-shadow and cache routing were added, but patch collection still mounted the clone read-only; denial-test source text evaluated an unescaped outer f-string name; exact and source probe fixtures remained inconsistent; and legacy commit, out-of-scope, and clean-filter tests still expected post-worker behavior that the physical mount now denies inside the worker.
- Implement two explicit Bubblewrap mount modes: worker mode uses read-only clone plus scratch then shadow binds, while patch-collection mode uses a writable temporary clone without shadows and still keeps host/source read-only. Update legacy tests to expect worker-time denial for `.git` mutation and unscoped writes. Configure the malicious clean filter through scratch HOME/global Git config, not writable clone `.git` metadata. Create every exact-scope fixture file before the baseline commit, escape generated worker-script braces, and pass `manifest.json` rather than `candidate.patch` to the apply command.
- Sandbox candidate `48061983cc1d35255df40f080c4df8928186c4fa17eac07f10be3fd849add15f` passed 23 of 24 host-side focused tests, runner self-test, default-prompt runtime evaluation, diff check, and root/template parity. The only failure is `test_bubblewrap_probe_blocks_source_and_host_temp_writes`, whose exact `probe.txt` scope target is absent from the committed fixture baseline. Preserve the accepted runner implementation and fix that fixture precondition before final validation.
- Rejected sandbox candidate `08ecee7628dd50f8ba0c712a05ca266905a2aae36e4a89debcd3282336e1f8ff` after main-session review despite all listed commands passing in its review clone: `SANDBOXED_PLAN_WORKER_PLAN_PATH` was assigned twice, while `PIP_CACHE_DIR` and `PYTHONDONTWRITEBYTECODE` were absent and no focused assertion covered the required cache routing. Preserve the otherwise accepted physical-mount implementation, correct only this environment setup and its focused test, and rerun all validations.
- Rejected sandbox candidate `b3098159140f7b8ed0d518fbbb2b5b9b6830e72f8a56ddace3134f2910baec88` during main-session patch review before host validation: `prepare_writable_shadows()` accepted an exact-scope directory or symbolic link and delegated both to the generic copy helper. This violates the exact-file contract and leaves mount-target resolution ambiguous. Preserve the cache-routing correction, require an existing non-symlink regular file for exact scope, preserve contained symlinks only while copying prefix trees, and add direct rejection tests for both invalid exact targets.
- Rejected sandbox candidate `c2500885fcc5da1c9ca4abf31ebd0732576194344df0c9f59ba6d7ae2ae7089c` during main-session path review before host validation: it rejected a symbolic link at the mount target but did not reject a symbolic-link ancestor. A scope such as `link/new/`, where `link` resolves elsewhere in the clone, could make trusted shadow preparation or materialization traverse outside the normalized scope. Reuse the existing component-walk guard against the candidate clone before any target creation or copy, and add a regression test that proves no path is created through the link.
