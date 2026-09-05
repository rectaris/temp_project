# Preserve project-owned agent model settings during Copier updates

status: backlog
primary_invariant: Copier preserves every existing project-owned agent model and reasoning value, fills only absent defaults, and rejects unrelated profile changes without altering the qualified writable-runner model policy.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"copier.yml invokes scripts/update_agent_model_profiles.py after rendering; render_profile currently overwrites existing model and model_reasoning_effort fields."}
  - {"kind":"existing_mechanism","evidence":"scripts/validate-copier-update.py validate_agent_profile_transition and template ownership.yaml explicitly permit fixed model-field replacement; tests/copier-update.sh asserts that customized values are overwritten."}
  - {"kind":"existing_mechanism","evidence":"The updater already parses TOML, preserves multiline instructions, rejects duplicate or unsafe inputs, and has idempotence and missing-field tests."}
completion_conditions:
  - A mature Copier update preserves present model and reasoning fields, including custom profile names and unrelated TOML bytes, and adds only individually absent defaults.
  - Invalid or duplicate TOML assignments and unsafe profile paths still fail closed; unauthorized replacement of a present model field is rejected by the update diff validator.
  - New copies retain current seeded defaults, and supported historical update paths preserve project-owned files, plan history, and the exact legacy read-only worker migration exception.
  - Ownership declarations and current documentation describe fill-only defaults, while template seed checks and qualified runner model, effort, fallback, and access-error rules remain unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:1934b68ff18b13b9a17c4fb28293b7ff6938f8bab4cf4a818e0153fbdfd30bdb","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:52150cd63c6515fe7b1528cf24852cbf5b315f93d243fbf5de609907749a0999","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:ba49109edbaf31d707be1f6679376cd3e21a567064de375e6f3609b4e39bc066","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:33011e7bfec8726b9bc114e5392a89ee4aef5bb1c9032fc85e1d238ad2e65ddc","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/update_agent_model_profiles.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - README.md
  - template/README.md.jinja
  - references/template-development.md
  - tests/test-agent-model-profiles.py
  - tests/test-copier-migration.py
  - tests/copier-update.sh
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - copier.yml
  - scripts/run-sandboxed-plan-worker.py
  - references/orchestration.md
  - scripts/migrate-sequential-plan-worker.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - tests/copier-update.sh --require-copier
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Preserve existing project-owned profile values and accept only exact missing-default insertion or the already specified legacy worker migration, with behavioral Copier coverage for allowed and rejected diffs.
  - Keep new-copy seeds and qualified writable-runner routing unchanged while aligning current ownership and documentation with the non-destructive update rule.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a4eb6e785b19d78f7b74659193d12533ff76b9592877a09af5a3a10d18a05f2a","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:85028132040769c78f91a90d17fd2161255c1bd94243b0bf992c17f423d8f576","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Use bounded parent implementation because Copier ownership and its validating authority change; obtain independent read-only review.
  - Keep copier.yml as the generation/update interface and retain its existing source-package task path; the updater is packaging-only and does not need a new installed template duplicate.
  - Mirror update validation behavior into the existing generated validator and express the same ownership rule in generated ownership.yaml and adoption documentation.
  - Treat existing fields as project-owned even when they equal an older seed; do not infer permission to upgrade them from equality.
  - Preserve the exact already-supported legacy sequential-worker migration exception; never generalize it to customized instructions or writable worker profiles.
  - Do not modify runner qualification, model availability classification, fallback count, sandbox policy, or seeded TOML values.
  - Keep historical changelog statements accurate as history; update checks of current policy without erasing release records.
  - The focused Copier command must include the mutable source files in its disposable fixture and fail if Copier is unavailable; do not accept a skipped update test.
checked_summary_ja: Copier 更新で利用側のモデルと推論設定を保持し、欠落項目だけを既定値で補うようにする。

## Decisions

- 対象は、Copier が既存の .codex/agents/*.toml の model と model_reasoning_effort を更新する処理である。
- モデル設定を上書きする処理と、その上書きを正当な差分として受け入れる検査を一緒に修正する。
- 既存の値が無効または利用不能に見えても、別のモデルへ自動置換しない。
- 構文不正は拒否し、構文上有効な設定の利用可否は利用側に残す。
- model と model_reasoning_effort を個別に扱い、片方だけが欠落した場合はその項目だけ補う。
- 既存ファイルに欠落項目を追加する以外は、コメント、改行、インデント、指示文を保持する。
- 書込み runner が許可するモデルの集合は、本プランの設定保持とは独立した既存の制約として残す。

## Tasks

- [ ] Replace normalization expectations with preservation fixtures, including custom values, one missing field, both missing fields, nested and multiline model-like text, idempotence, duplicates, and symlinks.
- [ ] Change render_profile to preserve existing assignments and insert only absent root fields, without moving the packaging helper or changing seeded profiles.
- [ ] Change the update validator to compare before/after ownership at field granularity and allow only exact missing-default insertion plus the existing exact historical migration.
- [ ] Update generated ownership and current root/generated docs; adjust current-policy marker checks while keeping safety and seed assertions.
- [ ] Extend the disposable Copier fixtures with preservation and malicious-overwrite failures; retain every supported historical migration fixture.
- [ ] Run the focused update suite, obtain independent review, and run authoritative validation once; the lint suite also executes the updater and migration unit tests.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.
