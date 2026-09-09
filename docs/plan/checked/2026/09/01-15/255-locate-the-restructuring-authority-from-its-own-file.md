# Locate the restructuring authority from its own file

status: checked
primary_invariant: a prospective repository verification re-invokes the same authority file that is already running, so plan restructuring succeeds in every layout that ships the authority, not only in a repository that happens to keep a copy at scripts/restructure-plan.py
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: low
implementation_ambiguity: low
implementation_tier: 1
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/backlog/253-restore-the-copier-update-replan-fixture.md
  - scripts/project_workflow/copier_inventory.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-plan-restructure.py PlanRestructureTest.test_prospective_verification_runs_from_a_generated_project_layout
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
acceptance:
  - Locate the plan restructuring authority from its own file so a generated project whose only copy lives under .project-agent-workflow/scripts can complete a prospective repository verification, and cover that layout with a regression test.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:dfb0d9e6e2b7c53bb6a5f1a949debd6c4b8275cd7965466518986b7304158fad","stage":"focused","witness":"python3 tests/test-plan-restructure.py PlanRestructureTest.test_prospective_verification_runs_from_a_generated_project_layout"}
integration_gates:
  - keep scripts/restructure-plan.py byte-identical to template/.project-agent-workflow/scripts/restructure-plan.py
  - do not relax any check the prospective verification performs; change only where the authority file is found
checked_summary_ja: 見込みリポジトリ検証が自分自身のファイルを起点に権限を再実行するようにし、生成project配置でもplan再構築が完了することを回帰testで固定する。

## Decisions

- The defect is real and independently reproduced. `verify_prospective_repository` hardcodes the ROOT-relative path `scripts/restructure-plan.py`, but a generated project receives the authority only at `.project-agent-workflow/scripts/restructure-plan.py` (`scripts/project_workflow/copier_inventory.py:387`). Every plan restructuring transaction in a generated project therefore fails.
- Re-invoke `Path(__file__).resolve()`. The parent process is the authority that just admitted the operations, so verifying the prospective state with that same file is both correct and layout-independent. Line 742 already derives the sibling command policy this way, so the fix restores an existing convention rather than inventing one.
- Do not copy the authority into the snapshot and do not search for it. Either would add a second, weaker way to decide which rules apply.
- The path was untested because every existing fixture copies the authority to `scripts/restructure-plan.py` (`tests/test-plan-restructure.py:59`), and the Copier update suite only runs `--verify` in the generated project. Add a regression test that builds the generated-project layout instead.

## Tasks

- [x] Reproduce the failure in a generated-project layout.
- [x] Add the regression test to `tests/test-plan-restructure.py`.
- [x] Derive the re-invoked authority path from `__file__` in both authority copies.
- [x] Run focused validation, then one independent review, then the authoritative suite.

## Validation Notes

- 診断の受領元は Plan 253 の停止記録である。Plan 253 は fixture 由来の失敗を 3 件修復した後、本欠陥に到達して停止した。
- 再現は独立に取得済みである。`tests/test-plan-restructure.py` の fixture を、権限が `.project-agent-workflow/scripts/` にのみ存在する配置へ組み替えて再構築 transaction を実行すると、0.2 秒で `prospective repository verification failed: ... /repository/scripts/restructure-plan.py: No such file or directory` が再現する。候補修正の適用後は同じ実行が成功する。
- 本 plan は Plan 253 から acceptance を引き継がない。Plan 253 が停止時に分類した独立修復そのものであり、それ以上ではない。
- 権威 validation は 4 件すべて通過した。`tests/test-plan-restructure.py` 175 件 OK（100 秒）、`scripts/check-copier-template.py` 通過、`--verify` 通過、`git diff --check` 清浄。
- 独立 review を 1 巡実施した。code 変更と回帰 test に指摘はなく、Medium 1 件は Plan 253 の記録欠落だった。訂正した所見を Plan 253 に復元して解消した。
- 権威 Copier 更新 suite は本 plan の validation に含めない。Plan 253 が停止中であり、その suite の完全通過は Plan 253 再開時の acceptance である。
