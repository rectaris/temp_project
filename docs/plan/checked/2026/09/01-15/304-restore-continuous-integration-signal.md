# Restore the continuous integration signal and let the sandboxed worker run on an account that has no Codex home

status: checked
primary_invariant: Every repository check that passes on a maintainer machine reaches its own assertions elsewhere instead of failing on a missing dependency, a missing commit, or host state the check never intended to require.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Run 34347469336 on 2026-09-09 failed three jobs. validate and minimum-compatibility raised ModuleNotFoundError: No module named 'yaml' from scripts/check-copier-template.py, and sandboxed-plan-worker raised both a git show failure for commit 006056f and 'hidden sandbox path must be an existing regular directory: /home/runner/.codex'.","kind":"reproduced_defect"}
  - {"evidence":"The validate and minimum-compatibility jobs already check out with fetch-depth 0, and the validate job already runs uv sync, so the workflow already carries both mechanisms this change extends to the jobs that lack them.","kind":"existing_mechanism"}
  - {"evidence":"Under a home directory without a Codex home, scripts/run-sandboxed-plan-worker.py aborts with 'hidden sandbox path must be an existing regular directory' because it adds the host Codex home to the hidden set unconditionally, including on the validation path that deliberately excludes the Codex home.","kind":"reproduced_defect"}
  - {"evidence":"The same function already appends the host home directory to the hidden set only when it is a directory, so the conditional shape this change applies to the Codex home is the shape the surrounding code already uses.","kind":"existing_mechanism"}
completion_conditions:
  - The continuous integration jobs that execute repository Python checks resolve python3 to the environment synced from pyproject.toml on the interpreter the job declares, so an import of a declared dependency succeeds.
  - The sandboxed plan worker job checks out the history its fixtures name, so a fixture commit lookup resolves.
  - The sandboxed plan worker hides the host Codex home only when the account has one, and still refuses a Codex home that exists but is not a regular directory.
completion_witness_map:
  - {"condition_sha256":"sha256:0a33a36c96d9b25839ed42658ba09e24bc3abe30d36c919112c7ec39cb1916fe","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:5cb3072a6ad3bdf284abc4814d19cd4b89e8fbe85639daf2d9b59ed457648c5c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:91b3f09de447c25f07c11522a774c87dac040aa1d65396cba51b1db5e004f6c6","witness":"python3 tests/test-sandboxed-plan-worker.py"}
write_scope:
  - .github/workflows/ci.yml
  - tests/test-sandboxed-plan-worker.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - pyproject.toml
  - tests/copier-minimum.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Every continuous integration job reaches the assertions it exists to make, so a failure reports a repository defect rather than an absent dependency, an absent commit, or absent host state.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:dafc899260a8e3e59ecbd8fb627f295a86518e0316e09db0eb46b91ea8e3ed5a","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
checked_summary_ja: CI の検証信号を回復し、Codex ホームの無いアカウントでもサンドボックス実行を可能にする

## Decisions

- Put the synced environment on PATH for the whole job rather than prefixing each step with uv run, because the repository scripts invoke python3 through nested shell layers that a per-step prefix would not reach.
- Pin uv sync to the interpreter the job already selected, so putting the synced environment first on PATH cannot silently move a job to a different Python version than the one it declares.
- Supply the dependencies rather than removing the yaml import from scripts/check-copier-template.py, because scripts/check-root-agent-policy.py imports yaml as well and the same suite runs it, so removing one import would leave the job failing.
- Hide the host Codex home only when it exists rather than giving the test suite its own Codex home, because an absent directory holds no credentials to expose and a suite-level override would leave the same failure waiting for any downstream account that has never run Codex.
- Check out full history for the sandboxed plan worker job rather than rewriting the fixture, because the fixture asserts against a real historical commit and the two other jobs already check out full history for the same reason.
- Keep passing an existing Codex home that is not a regular directory into the hidden-path check, so the change removes the absent-home failure without relaxing the check that rejects an unexpected Codex home shape.

## Tasks

- [x] Pin the synced environment to the declared interpreter and place it first on PATH for the jobs that run repository Python checks.
- [x] Check out full history for the sandboxed plan worker job.
- [x] Hide the host Codex home only when it exists, mirror the runner into the template, and cover the absent, present, and non-directory cases with a test.
- [x] Run the focused witness under a home directory without a Codex home and under the ordinary home, then the authoritative suite once.

## Validation Notes

- 焦点証人 `python3 tests/test-sandboxed-plan-worker.py` は、Codex ホームを持たない一時 HOME でも通常の HOME でも 147 件すべて成功した。修正前の同一証人は前者で `test_apply_finalization_failure_leaves_recoverable_applying_state` が失敗する。
- 権威検証は `scripts/lint-project-workflow.sh` と `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` を各 1 回実行し、いずれも通過した。lint 出力中の `root agent policy check failed:` 行は否定試験の期待出力である。
- `actionlint` 1.7.12 を導入し、`REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .` が無指摘であることを確認した。
- 独立レビュー（gpt-5.6-sol、読み取り専用）は、テスト側で `CODEX_HOME` を一括指定する当初案が新規アカウントで再現する runner 側の欠陥を隠すと指摘した。指摘を受け入れ、runner 側で「存在するときだけ隠す」条件に改め、テスト側の一括指定を撤去した。受理判断は本セッションが保持する。
