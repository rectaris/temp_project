# Integrate validation-witness migration provenance

status: checked
primary_invariant: the accepted guardian protocol, policy, source inventory, and genuine Copier transition jointly prove the Plan 163 migration boundary before downstream witness enforcement begins
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - tests/smoke.sh
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/180-admit-live-validation-witness-guardian.md
  - docs/plan/checked/2026/08/16-31/181-verify-plan176-successor-acceptance.md
  - docs/plan/checked/2026/08/16-31/177-align-validation-witness-provenance-policy.md
  - docs/plan/shelved/184-verify-plan178-successor-acceptance.md
  - docs/plan/replanned/2026/08/16-31/163-capture-validation-witness-migration-provenance.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - pytest tests/test-copier-migration.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"the genuine pre-update boundary requires a complete versioned Copier transition from a clean committed downstream project"}
predecessor_plans:
  - docs/plan/shelved/184-verify-plan178-successor-acceptance.md
replan_source: docs/plan/active/163-capture-validation-witness-migration-provenance.md
replan_contract: docs/plan/replanned/contracts/163-capture-validation-witness-migration-provenance.json
integration_gates:
  - Plans 180, 181, 177, and 184 must be checked and their exact checked archive paths must replace active context paths before integration starts
  - validation-witness-migration-integration-gate requires all focused checks and independent review to report zero unresolved High or Medium findings
  - run the Plan 163 authoritative Copier transition exactly once and make its checked archive the only migration dependency consumed by Plan 165
successor_plans:
  - docs/plan/active/176-establish-live-validation-witness-provenance.md
  - docs/plan/active/177-align-validation-witness-provenance-policy.md
  - docs/plan/active/184-verify-plan178-successor-acceptance.md
  - docs/plan/active/179-integrate-validation-witness-migration-provenance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: guardian protocol、方針、inventory、実際のCopier更新を統合し、旧形式witness移行境界を確定する。

## Decisions

- validation-witness-migration-integration-gate means the condition that every migration slice and the real versioned transition pass without unresolved High or Medium review findings.
- Treat checked Plans 180 and 181 as the durable replacement for replanned Plan 176, checked Plan 177 as the policy slice, Plan 184 as the acceptance gate for replanned Plan 178, and this plan as their combined acceptance boundary.
- Replace predecessor active paths with exact checked archive paths only after each predecessor is accepted.
- Keep the narrower focused checks executable before the sole authoritative v1.4.4-to-v1.4.5 Copier transition.
- Make this checked plan, rather than any individual implementation slice or the replanned Plan 163 archive, the migration dependency consumed by Plan 165 and the remaining Plan 130 chain.
- Verify policy markers, template checks, and checker behavior read-only; if reconciliation requires a path outside CHANGELOG.md or tests/smoke.sh, enter replan_required instead of editing it here.
- Treat this complete Copier update as the Plan 163 lineage boundary; Plan 166 and Plan 167 retain their own later authoritative executions.

## Tasks

- [x] Confirm Plans 180, 181, 177, and 184 are checked and refresh their exact archive paths.
- [x] Verify policy markers, template checks, and checker behavior, and change only smoke coverage and the Unreleased record when needed.
- [x] Complete focused validation and independent read-only review with zero unresolved High or Medium findings.
- [x] Run the Plan 163 authoritative Copier transition exactly once, archive, commit, and activate Plan 165 with this exact checked predecessor.

## Validation Notes

- This plan validates only the replacement for Plan 163. Plan 167 retains the unchanged complete Plan 130 authoritative suite.
- 権威検証 `tests/copier-update.sh --require-copier` は exit status 1 で失敗した。失敗箇所は `tests/copier-update.sh:1145`、報告は `plan restructuring failed: successors[0] requires validation_witness_schema: 1`。
  原因は `tests/copier-update.sh:1075-1116` の replan fixture が `status: in_progress` の後継planを `focused_validation`・`validation_witness_schema`・`validation_witness_map` なしで生成することにある。witness要求は 2026-08-24 の `0ad400f` で入り、fixture は追随していない。本plan、commit `1368f40`、commit `97de2d1`、および未commitの `CHANGELOG.md`・`tests/smoke.sh` はいずれも `validation_projection` にも当該fixtureにも触れていない。
  影響するinvariantは本planのprimary invariantで、真正なCopier遷移自体が開始できない。独立reviewの確認済み判定は `repair_required` であり、修復対象は `tests/copier-update.sh` 一つに閉じる。本planの実行は停止し、再開は fixture 修復が checked になった後の新しい実行として行う。
- Plan 184 は所有者判断で `docs/plan/shelved/184-verify-plan178-successor-acceptance.md` に見送られたため、`integration_gates` が求める「184 が checked であること」は waiver とする。この waiver が省く保証は、Plan 178 の後継計画が受入項目を過不足なく引き継いだことの独立検証である。Plan 184 が backlog または active に戻った時点でこの waiver は失効し、ゲートは再び拘束する。
- 停止条件は解消された。分類済みの独立修復は Plan 253 と Plan 255 として checked になり、Plan 253 の記録は権威 suite `tests/copier-update.sh --require-copier` が完全通過したことを示している。所有者指示により、本 plan は backlog から新しい実行として再開する。
  上の診断は修復対象を `tests/copier-update.sh` 一つと述べているが、実際の修復は Plan 253 の `tests/copier-update.sh` と Plan 255 の `scripts/restructure-plan.py` の二つに及んだ。これは Plan 253 が自らの write scope を広げず二件目の欠陥を報告して停止した結果であり、独立修復の境界規則が働いた形である。
- 再開後の限定検証は 4 コマンドすべて通過した。`pytest tests/test-copier-migration.py` は 31 件と subtest 48 件が成功し、`python3 scripts/check-root-agent-policy.py`、`python3 scripts/check-copier-template.py`、`git diff --check` はいずれも exit 0 で終了した。
  repository 全体の必須検証も併せて実行し、`tests/smoke.sh` と `scripts/lint-project-workflow.sh` がどちらも exit 0 で通過した。
- 独立 review を 1 巡と再審 1 巡実施し、未解決の High および Medium はゼロで終了した。review は write scope 逸脱がないこと、`scripts/check-copier-template.py` と `tests/copier-update.sh` が preservation scope として無変更であること、smoke の 3 つの assertion が生成 project の実在文字列に一致すること、CHANGELOG が実装以上の主張をしていないこと、backlog から active への再開が lifecycle evolution の許す範囲であることを機械的に確認した。
  review が最初に提起した Medium は、本 plan が追加した `tests/smoke.sh` の 3 行を manifest 記載のどのコマンドも実行しない、というものだった。再審の結果これは取り下げられた。受入項目の witness は真正な版遷移を要する `tests/copier-update.sh --require-copier` であり、より狭い安全な事前検証は存在しない。3 行の内容は限定検証の `scripts/check-root-agent-policy.py` が root と template の双方に対して既に強制しており、生成後の残余部分は `AGENTS.md` が完了前に義務付ける `tests/smoke.sh` で実行済みである。
  この witness の所在は記録として残す。3 つの assertion を実行する権限は plan manifest ではなく repository 全体の必須検証にある。この配置は本 plan の変更が作ったものではなく、replan contract 束縛時点から `tests/smoke.sh` は write scope にあり `validation` には無い。
- 権威検証 `tests/copier-update.sh --require-copier` を 1 回だけ実行し、exit 0 で完全通過した。suite は `copier update test passed` まで到達し、受入項目が要する v1.4.4 から v1.4.5 への版遷移を実行した。
  遷移後の生成 project は `.copier-answers.yml` に `_commit: v1.4.5` を持ち、`.project-agent-workflow-migration/validation-witness-provenance-v1.json` に `"migration_version": "v1.4.5"` を記録し、rejection file を残さなかった。これにより guardian protocol、方針、source inventory、真正な Copier 遷移が揃って Plan 163 の移行境界を証明した。
