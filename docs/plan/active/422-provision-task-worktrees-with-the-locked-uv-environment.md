# Create each new task worktree's .venv with uv sync --locked and run root validation through uv run --locked

status: in_progress
primary_invariant: Every newly prepared task worktree of a project that ships pyproject.toml and uv.lock has its own .venv synced exactly to uv.lock before work starts, validation runs inside that environment, and a sync failure is reported instead of leaving an unprovisioned worktree silently in use.
task_types:
  - task_worktrees
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
standing_continuation_authorization: 420 プランはすでに実装されているため、 こちらに 4回レビューまで承認を求めなくともよいようにしていたはずだが
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"references/validation.md already prescribes uv sync --locked and uv run --locked scripts/lint-project-workflow.sh, tests/smoke.sh and tests/copier-update.sh, and pyproject.toml with uv.lock pins ruff 0.15.7, copier and PyYAML, but manage-plan-worktrees.py create_worktree provisions no environment.","kind":"existing_mechanism"}
  - {"evidence":"On 2026-09-26 validation in fresh task worktrees failed with Ruff is unavailable until the main checkout's .venv/bin was put on PATH, because no worktree had its own .venv.","kind":"reproduced_defect"}
  - {"evidence":"create_worktree already runs one post-checkout step, normalize_required_hook_modes, before writing the ownership record, which is the place a bounded environment step can follow.","kind":"existing_mechanism"}
completion_conditions:
  - prepare runs uv sync --locked in a newly created task worktree whose checkout contains both pyproject.toml and uv.lock, before it reports the worktree, and records the outcome in its JSON report.
  - prepare skips provisioning with a stated reason when either file is absent or when resuming an existing worktree, and when uv is missing or the locked sync fails it exits nonzero, names the retry command and keeps the created worktree and its ownership record.
  - The sync runs with --locked and --no-python-downloads, the worktree as its working directory, a bounded timeout and no inherited VIRTUAL_ENV or UV_PROJECT_ENVIRONMENT, writes only the worktree's .venv and the user uv cache, and a missing compatible interpreter fails preparation.
  - AGENTS.md, references/validation.md and references/template-development.md require running the declared root validation commands unchanged inside the task worktree's environment, through uv run --locked or an activated .venv, and the root policy checker asserts that rule.
  - Both manage-plan-worktrees.py copies stay byte-identical, and both SPEC_PLAN_WORKFLOW.md copies describe the provisioning step in the task worktree boundary.
completion_witness_map:
  - {"condition_sha256":"sha256:204e97b7112de70aea826d7c5522a49c5ad673f0e512ebf92c1dcf92c6df246f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:e08a5fbd3f8b0e17fd704dcd03b935ac137811f88990571ca2d7a96742fb76ce","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:08cef47c7592f22c8d684c7f6d25d098938f6a1a1030810287d622ba8e5d32fa","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:c6541089554b669d8edd29e6196662cf9a9b42856f6c93a1e942725b7e51b162","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:ab444705963dedb8809210236e6a67a99af27f3d326c79db4d88cb7ca2e84fdf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/manage-plan-worktrees.py
  - tests/validation_tools/worktrees.py
  - AGENTS.md
  - references/validation.md
  - references/template-development.md
  - scripts/check-root-agent-policy.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - pyproject.toml
  - uv.lock
  - .github/workflows/ci.yml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A newly prepared task worktree of a uv-locked project has its own .venv synced to uv.lock before work starts, or preparation reports why it does not.
  - Root validation runs through uv run --locked in the task worktree, so the pinned Ruff and dependencies come from uv.lock rather than another checkout.
  - Generated projects without uv.lock prepare worktrees exactly as before.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:424b805ea24fb045d9e7c841321a2bc725c500a455818fb139dc8998dff2e0c4","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:b7c6b848d7eadbcf6d28142aee1c4a88ceda18d0ce294f530b506f74a0b61aa1","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:e57c31b88b798990a3c432dc67d58d1b1d6da660646db412158f682617efba9b","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 新しいタスクの worktree を作るときに uv sync --locked で .venv を作り、ルートの検証を uv run --locked で実行する規則にする。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct.
- Provision only newly created worktrees whose checkout carries both pyproject.toml and uv.lock, by running uv sync --locked there after the hook-mode normalization and before the ownership record is reported. Resumed worktrees are not re-synced.
- Fail visibly: a missing uv or a failed locked sync makes prepare exit nonzero with the retry command, and the worktree and its ownership record stay so the task can resume.
- Clear VIRTUAL_ENV and UV_PROJECT_ENVIRONMENT for the sync, pass --no-python-downloads so uv never installs an interpreter, bound it with a timeout, and use the default user uv cache.
- Make uv run --locked the root validation rule in AGENTS.md and fix references/template-development.md, which still shows unlocked uv sync and bare commands. Leave CI workflows unchanged in this plan.
- Keep declared validation commands unprefixed and the validation-command allowlist unchanged; the rule governs how the parent executes them, not what a plan declares. Until the interpreter plan is checked, run tests/test-sandboxed-plan-worker.py with the system python3.

## Tasks

- [ ] Record the unchanged prepare and worktree test results before product edits.
- [ ] Add the provisioning step, skip reasons, failure reporting and bounds to both worktree-manager copies.
- [ ] Add cases with a fake uv for success, missing files, resume, missing uv, sync failure and environment isolation.
- [ ] State the uv validation rule in AGENTS.md, both references and the root policy checker, and describe provisioning in both SPEC_PLAN_WORKFLOW.md copies.
- [ ] Obtain independent review through a fresh read-only reviewer, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26 asked to define these environment and workflow changes as rules and to create plans for them: create each task worktree's .venv with uv, let Bubblewrap run the .venv Python, replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium, fix the check-time plan-id reservations, and approve continuations up to the fourth review once at plan start (option A).
- standing_continuation_authorization quotes the owner's words of 2026-09-27, given in the plan 421 conversation after it asked twice for continuation approval. The owner then chose to record that approval in the plan file (「2 の計画で作成する。」); plan 424 added the field here.
