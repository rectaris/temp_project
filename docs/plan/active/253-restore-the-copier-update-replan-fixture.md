# Restore the Copier update replan fixture

status: in_progress
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

- [ ] Add `focused_validation`, `validation_witness_schema`, and one mapped `validation_witness_map` entry to the fixture plan template in `tests/copier-update.sh`.
- [ ] Run the authoritative suite and record whether it reaches the versioned v1.4.4-to-v1.4.5 transition.
- [ ] Report any newly exposed failure without repairing it here.

## Validation Notes

- Plan 179 の権威検証が `tests/copier-update.sh:1145` で停止したことを独立 review が確認し、`repair_required` と判定した。本 plan はその判定に対応する唯一の修復である。
- fixture 修復後、権威 suite は同じ地点で 2 度前進し、`preservation_scope` 欠落も同 fixture 由来として同時に直した。
- 3 度目の実行で fixture 由来ではない失敗に到達した。`plan restructuring failed: [Errno 2] No such file or directory: .../docs/plan/replanned.md`。
  原因は `scripts/restructure-plan.py:4484-4491` にある。行 4486 は `docs/plan/replanned.md` の不在を許容して `rows` を空にするが、直後の `historical_contract_snapshot(rows)` は行 380 で同じ file を無条件に読むため、index を持たない project の最初の plan 再構築は必ず crash する。
  これは生成 project に出荷済みの製品欠陥であり、fixture の問題ではない。本 plan の write scope は `tests/copier-update.sh` に閉じており、gate は「露見した以降の失敗は本 plan で直さず報告する」と定めている。よって本 plan の実行はここで停止し、所有者の判断を待つ。
