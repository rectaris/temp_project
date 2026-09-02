# Integrate validation witness enforcement

status: checked
primary_invariant: the combined successor state proves every Plan 130 acceptance clause through its earliest parent-owned witness while preserving the complete authoritative suite
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
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/smoke.sh
preservation_scope:
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/checked/2026/08/16-31/164-bind-replan-contract-validation-baseline.md
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
  - docs/plan/checked/2026/09/01-15/166-unify-copier-update-source-inventory.md
  - docs/plan/checked/2026/08/16-31/131-require-confirmed-failure-diagnosis.md
  - docs/plan/checked/2026/08/16-31/171-integrate-session-resource-boundaries.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-root-agent-policy.py --include-holdout
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/checked/2026/08/16-31/164-bind-replan-contract-validation-baseline.md
  - docs/plan/checked/2026/09/01-15/165-enforce-validation-witness-maps.md
  - docs/plan/checked/2026/09/01-15/166-unify-copier-update-source-inventory.md
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plans 179 and 164 through 166 must be checked and their exact checked archive paths must replace active context paths before integration starts
  - checked Plans 131 and 171 remain read-only; Plan 192 must receive this exact checked predecessor before activation
  - run the source authoritative suite exactly once only after focused validation and independent review report zero unresolved High or Medium findings
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 旧形式移行、再計画契約、witness検証、Copier inventoryを統合して最終検証する。

## Decisions

- validation-witness-integration means the final combined acceptance and authoritative-validation boundary for all Plan 130 successors.
- Treat Plan 179 and Plans 164 through 166 as the only operational implementation predecessors and this plan as the combined Plan 130 acceptance boundary.
- Refresh active dependency paths only after each predecessor is checked and do not alter accepted requirements.
- Reconcile root and generated policy checks, retain the original authoritative command order, and require independent read-only review before the one authoritative run.
- Use bounded parent implementation because integration checks and active-plan witness mappings are validation authority.

## Tasks

- [x] Confirm Plan 179 and Plans 164 through 166 are checked and refresh their exact archive paths.
- [x] Reconcile policy markers, smoke coverage, and the Unreleased record without editing checked Plans 131 or 171; parent lifecycle then activates Plan 192 with this exact checked predecessor.
- [x] Complete focused validation and independent review with zero unresolved High or Medium findings.
- [x] Run the unchanged Plan 130 authoritative suite exactly once, archive, commit, and refresh Plan 133 to this checked archive.

## Validation Notes

- The source authoritative suite was never run under Plan 130 and remains available for this final integration plan.
- This plan's complete Copier update is the Plan 130 integration boundary and remains distinct from the Plan 179 and Plan 166 authoritative runs.
- `successor_plans` preserves the immutable Plan 130 lineage; Plan 179 replaces the replanned Plan 163 member in operational dependencies, and Plan 192 is the next operational plan after this gate.
- `integration_gates` の二つ目が求める Plan 192 への checked predecessor 引き渡しは waiver とする。
  Plan 192 は `docs/plan/shelved/192-freeze-resource-evaluation-contract.md` にあり、`status: shelved` である。
  shelved plan は実行しないとオーナーが決めた plan であり、それを待つ gate は満たされることがない。
  この waiver が省く保証は、本planの checked archive path を Plan 192 の `predecessor_plans` と `integration_gates` へ実際に反映することである。
  Plan 192 が `docs/plan/backlog/` または active 索引へ戻った場合、この義務は再び有効になる。
- checked Plans 131 と 171 は read-only のまま扱い、本planの `write_scope` にも含めない。
- 統合前の状態では、witness map の方針文を root と生成側の双方で弱められることを実測した。
  root `AGENTS.md`、`references/orchestration.md`、生成側の `AGENTS.md.jinja` と `SPEC_ORCHESTRATION.md` から最終検証suiteを弱めない条件を削っても、既存の検査はすべて成功した。
  Copier 更新の単一 inventory から `template/.project-agent-workflow/scripts/plan_validation_commands.py` を削っても同様に成功した。
  本planはこの二つを `scripts/check-root-agent-policy.py` と `scripts/check-copier-template.py` の限定検証で拒否するようにした。
- 独立reviewを1回実施し、Medium 1件と Low 1件を得た。
  Medium は orchestration 側の拒否条件文と適用条件が marker で固定されておらず、root と生成側を同時に書き換えると検査を通過する、というものである。
  `a new or materially updated` を共通 marker へ、拒否条件文を orchestration marker へ追加して閉じた。追加後は片側改変、両側同時改変のいずれも拒否することを実測した。
- Low は受入条件の第2節の証拠範囲に関するものである。
  生成側の実装は authoritative witness が `focused_validation` の宣言と文字列一致する場合に拒否する。
  したがって smoke が示すのは「宣言済みの限定検証commandと同一のcommandを最終検証段として対応付けること」の拒否であり、より広い「安全な限定検証が構成可能である」ことの判定ではない。
  この境界は checked Plan 165 が定めた実装に由来し、本planの `write_scope` の外にある。要求の変更ではなく証拠範囲の明示として記録する。
- smoke の新規assertionが空振りしないことを両方向で実測した。
  正例を最終検証専用の対応付けへ変えると `skips an available focused witness` で失敗し、負例の一つから改変を外すと `generated plan validation accepted an integration lane with no witness map` で失敗する。
- 独立reviewの2巡目を実施し、High と Medium は0件になった。残った指摘はLow 1件で、marker で固定していない文にも実行可能な裏付け（`scripts/check-copier-template.py` の planlib marker と本planが追加した smoke の否定例5件）があるという内容である。
- Plan 130 由来の最終検証suiteを、宣言順どおりに1回だけ実行し、9command すべてが成功した。
  `python3 tests/test-validation-tools.py`、`python3 scripts/check-root-agent-policy.py`、`python3 scripts/check-root-agent-policy.py --include-holdout`、`python3 scripts/check-copier-template.py`、`python3 scripts/validate-changes.py --all`、`scripts/lint-project-workflow.sh`、`tests/smoke.sh`、`tests/copier-update.sh --require-copier`、`git diff --check` である。
- Plan 133 への反映は、`docs/plan/replanned/2026/08/16-31/133-evaluate-resource-bounded-orchestration.md` の `context_files` が本planを指しているため、finalize 時の参照付け替えで行う。
  Plan 133 は `status: replanned` の確定記録であり、本文を書き換えることはしない。
- 補助として read-only の review agent を2回利用した。判断は助言として扱い、受入と記録は本session が行った。
