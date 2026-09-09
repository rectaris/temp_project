# Restore the Copier update replan fixture

status: checked
primary_invariant: the replan fixture the authoritative Copier update suite builds satisfies the same plan rules the current restructuring authority enforces, so that suite fails only on a real product defect and never on its own stale input
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: low
implementation_ambiguity: low
implementation_tier: 1
write_scope:
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/backlog/179-integrate-validation-witness-migration-provenance.md
  - scripts/restructure-plan.py
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - tests/copier-update.sh --require-copier
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
acceptance:
  - Restore the Copier update replan fixture so its in_progress successors declare the focused witness the current plan rules require, and prove the authoritative Copier update suite reaches its versioned transition again.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:1f5d7919f065226fa0752dc69ee3ecbe4ed1af30d97ac34d324a87599721fd8d","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"the fixture is built and consumed only inside that suite, so no narrower command can observe whether the restructuring transaction it drives now succeeds"}
integration_gates:
  - change only the fixture plan template; do not weaken any check in scripts/restructure-plan.py to make the fixture pass
  - report every further failure the repaired fixture exposes instead of repairing it in this plan
checked_summary_ja: 権威Copier更新suiteが自前で作るreplan fixtureを現行plan規則に追随させ、suiteが自分の入力で落ちない状態へ戻す。

## Decisions

- The defect is the fixture, not the authority. `scripts/restructure-plan.py` requires `validation_witness_schema: 1` for an `in_progress` plan, and the fixture predates that requirement. Repair the input and leave the check untouched.
- Declare the witness at `stage: focused` and add `focused_validation` to the fixture template. `git diff --check` is a safe narrower preflight, so declaring it `authoritative` inside the fixture would model the very shape the Plan 130 acceptance item rejects.
- This plan carries no source acceptance from Plan 179 and creates no replan contract. It is the bounded repair Plan 179's stopped run classified, nothing more.
- The suite stopped at 59% of its length. Treat any failure the repair exposes further along as a separate observation to report, not as work to absorb here.

## Tasks

- [x] Add `focused_validation`, `validation_witness_schema`, and one mapped `validation_witness_map` entry to the fixture plan template in `tests/copier-update.sh`.
- [x] Run the authoritative suite and record whether it reaches the versioned v1.4.4-to-v1.4.5 transition.
- [x] Report any newly exposed failure without repairing it here.

## Validation Notes

- Plan 179 の権威検証が `tests/copier-update.sh:1145` で停止したことを独立 review が確認し、`repair_required` と判定した。本 plan はその判定に対応する唯一の修復である。
- 修復は 3 段階進んだ。(1) `focused_validation` と witness 欄の欠落、(2) `preservation_scope` の欠落、(3) `docs/plan/replanned.md` の不在。いずれも fixture 由来である。
- (3) について、当初は `scripts/restructure-plan.py:4490` の無防備な読み取りを製品欠陥と診断したが、これは**誤診**だった。fixture は `latest_ref=v0.4.6` から project を生成する。`git show v0.4.6:template/docs/plan/` が示すとおり、この世代の template は `replanned.md` を持たない。現行の再構築権限が行 7476 で index の存在を要求するのは意図された仕様であり、fixture が `docs/plan/plan.md` と同様に空 index を用意すべきだった。誤った修正は破棄し、fixture 側で直した。
- 4 度目の実行で、fixture 由来ではない失敗に到達した。`prospective repository verification failed: ... /repository/scripts/restructure-plan.py: No such file or directory`。
  `scripts/restructure-plan.py:4700-4701` の `verify_prospective_repository` は、clone したsnapshot に対して `scripts/restructure-plan.py` という**根直下の相対 path を直書き**している。しかし生成 project が受け取るのは `.project-agent-workflow/scripts/restructure-plan.py` だけで（`scripts/project_workflow/copier_inventory.py:387`）、根直下の複製は存在しない。自分自身の位置は行 742 のように `__file__` から導出できるにもかかわらず、ここでは導出していない。
  生成 project による plan 再構築 transaction を通す test は存在しない（`tests/copier-update.sh:1158` は `--verify` のみ）。よってこの経路は一度も実行されていない可能性が高い。
  本 plan の write scope 外であり、gate の定めどおり修復せず報告して停止する。
- (3) の訂正に伴い残る所見を記録する。index が必須であるという結論は変わらないが、再構築 transaction 経路の扱いは `--verify` 経路と一致していない。`scripts/restructure-plan.py:4484-4487` は `REPLANNED_INDEX.is_file()` が偽なら `rows` を空にするが、直後の `historical_contract_snapshot` は行 379 で同じ file を無条件に読む。よってこの分岐は到達しない死んだ許容であり、index を持たない project では行 7476 が返すような明示的な拒否ではなく、文脈のない `FileNotFoundError` が表面化する。利用者に見える影響は誤解を招く error 文言に限られ、本 plan は fixture 側で index を用意したため再発しない。修復は本 plan の write scope 外である。
- 診断は独立に再現済みである。生成 project 配置（権限を `.project-agent-workflow/scripts/` に置き、根直下に複製を持たない）で plan 再構築 transaction を実行すると、0.2 秒で同一の失敗が再現する。所有者判断により、この製品欠陥は別の bounded 修復 plan で直す。本 plan の実行はここで停止し、再開はその修復が checked になった後の新しい実行として行う。
- 修復 Plan 255 が checked になったため、所有者指示により新しい実行として再開する。停止時に分類した独立修復は完了しており、本 plan は権威 suite の続きから確認する。
- 再開後の権威実行で `tests/copier-update.sh --require-copier` は完全通過した（exit 0）。suite は行 1947 の `copier update test passed` まで到達し、acceptance が求める v1.4.4 から v1.4.5 への版遷移（行 1687-1947）を実行した。2026-08-24 の `0ad400f` 以降初めて、この suite は自分の入力で落ちなくなった。
- 独立 review を 1 巡実施し、指摘はなかった。review は fixture transaction を独立に再演し、差分が純粋に追加のみであること、seed した index が欠陥を隠さないこと、witness の stage が拒否対象の形ではないこと、source plan 側の template を変更していないことを確認した。
- 露見した 2 件は gate のとおり修復せず報告した。うち 1 件は所有者判断により Plan 255 で修復済みである。残る 1 件（行 4484-4487 の死んだ許容分岐）は error 文言のみの影響であり、記録に留める。
