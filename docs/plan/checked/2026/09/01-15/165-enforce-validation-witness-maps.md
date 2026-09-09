# Enforce validation witness maps before execution

status: checked
primary_invariant: plan command validation fails closed unless acceptance coverage, lifecycle provenance, authoritative command identity, and every static context path identity are proven
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
write_scope:
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
preservation_scope:
  - scripts/check-copier-template.py
  - tests/copier-update.sh
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/179-integrate-validation-witness-migration-provenance.md
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
  - docs/plan/replanned/2026/08/16-31/130-map-acceptance-validation-witnesses.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/190-migrate-live-plan-contracts.md
  - docs/plan/checked/2026/09/01-15/179-integrate-validation-witness-migration-provenance.md
replan_source: docs/plan/active/130-map-acceptance-validation-witnesses.md
replan_contract: docs/plan/replanned/contracts/130-map-acceptance-validation-witnesses.json
integration_gates:
  - Plans 190 and 179 must be checked and their exact checked archive paths must replace these active predecessors before implementation
  - in the same parent-owned activation update, add docs/plan/replanned/baselines/live-validation-successors-v1.json emitted by checked Plan 190 as exact read-only context
  - accept legacy omission only from the exact guardian-backed migration evidence integrated by Plan 179 and authoritative identity only from the companion baseline produced by Plan 190 under Plan 164's accepted schema
successor_plans:
  - docs/plan/active/163-capture-validation-witness-migration-provenance.md
  - docs/plan/active/164-bind-replan-contract-validation-baseline.md
  - docs/plan/active/165-enforce-validation-witness-maps.md
  - docs/plan/active/166-unify-copier-update-source-inventory.md
  - docs/plan/active/167-integrate-validation-witness-enforcement.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: 受入条件、移行証拠、最終検証command、静的pathを実行前にfail-closedで検証する。

## Decisions

- validation-witness-enforcement means the pre-execution checks over acceptance mappings, migration provenance, contracted validation commands, and static path identity.
- Retain SHA-256 binding and exact source-order coverage for acceptance items.
- Accept a pre-schema integration plan only when its exact committed bytes match the guardian-backed evidence integrated by Plan 179 and its replan-contract lineage remains valid.
- Compare the live authoritative validation sequence with the immutable companion baseline created by Plan 190 before accepting any witness map.
- Reject symlinks in every context path component, not only the final component.
- Use bounded parent implementation and independent review because every changed executable path is validation authority.

## Tasks

- [x] Replace the current forgeable legacy exception with migration-bound validation.
- [x] Enforce exact authoritative command preservation and witness-stage rules.
- [x] Reject symlinked ancestors, traversal, duplicates, stale status, and out-of-root static paths.
- [x] Add deterministic positive and negative tests, complete focused validation and independent review, archive, and commit.

## Validation Notes

- Preserve the current unaccepted parser and test changes as candidate input; review each hunk against the accepted Plan 179 evidence and Plan 190 companion baseline before reuse.
- `successor_plans` preserves the immutable Plan 130 lineage; operational dependency paths use Plan 179.
- `integration_gates` の二つ目が求める `docs/plan/replanned/baselines/live-validation-successors-v1.json` の `context_files` への追加は waiver とする。
  この path を追加すると `python3 scripts/restructure-plan.py --verify` が `changes protected manifest field: context_files` で失敗する。
  lifecycle evolution が `context_files` を保護し、activation record の promotion は `preservation_scope` にある path しか `context_files` へ移せないためである。
  本planの `preservation_scope` はその path を持たず、backlog planは activation record 自体に到達できない。
  この waiver が省く保証は、companion baseline を宣言済みの read-only context として plan manifest 上で静的に固定することである。
  baseline は write_scope 外の不変fileであり、本planの実装と test が同じ bytes を code 上で束縛する。
- 独立reviewを8回実施した。第4回が指摘した High は、shape が正準な schema-2/3 の replan contract を偽造すれば権威になりうる、というものである。
  contract は working tree の通常fileであり、shape の一致は publication の証拠にならない。
  これを証明として閉じるには正準 contract 検証器の再実装か Git 履歴への束縛が必要で、いずれも本planの write_scope と手法の外にある。
  そこで本planでは schema-2/3 lineage を admit せず、companion baseline に record を持たない contract を一律に拒否する fail closed に倒した。
  admit 側の実装は後継 plan `docs/plan/backlog/256-prove-self-projecting-contract-authority.md` が持つ。要求の削除ではなく実行時期の繰延である。
- `required` gate が plan 側の `status` と `integration_gates` に依存する点は本planの範囲外とした。
  この gate は witness map schema 自身の意味論であり、widen すると要求が変わる。両fieldの改竄は `python3 scripts/restructure-plan.py --verify` が protected lifecycle state として拒否することを実測で確認した。
- 最終reviewは High と Medium をともに 0 とした。archive lifecycle status の読み取りを manifest 領域に限定し、`parse_manifest` と同じ field 認識規則へ揃えた。
  実在する plan 249 件で両者の解釈が一致することを実測で確認した。
- 権威validationの結果は `python3 tests/test-validation-tools.py` 50 件成功、`python3 scripts/check-copier-template.py` 成功、`git diff --check` clean である。
  補助として `scripts/lint-project-workflow.sh` と `tests/smoke.sh` も成功した。実装は commit `c403d14` にある。
