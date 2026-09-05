# Route detailed agent policy without losing mandatory requirements

status: backlog
primary_invariant: Every mandatory safety and lifecycle requirement remains directly reachable before its governed action, while always-loaded AGENTS files no longer duplicate task-specific migration and ledger procedures.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"At 987ed43 root AGENTS is 19694 bytes and managed template AGENTS is 19222 bytes; each contains the same 2071-byte guardian instruction. Replacing that duplicate with a required route of at most 300 bytes supplies a concrete margin for the 1000-byte reduction target."}
  - {"kind":"existing_mechanism","evidence":"AGENTS.md duplicates detailed migration guardian, execution ledger, review registry, and correction rules already routed through docs/agent/spec-index.yaml and normative workflow documents."}
  - {"kind":"existing_mechanism","evidence":"Generated managed AGENTS has task routing and SPEC_ORCHESTRATION.md; check-root-agent-policy.py and check-copier-template.py currently assert detailed markers and root/template alignment."}
  - {"kind":"existing_mechanism","evidence":"spec-index.yaml requires direct reads of normative documents and supplies small default communication/Japanese-writing reads, so routed details need not be compressed or removed."}
completion_conditions:
  - Each moved mandatory requirement has one canonical normative destination and a tested root/generated task route that requires the destination before the affected operation.
  - Root and generated managed AGENTS each remove at least 1000 UTF-8 bytes from their activation baseline, without removing core authority, direct-read, stop, validation, or routing instructions.
  - Fixed static median and edge scenarios reject missing or dangling routes, skipped required policy, lost migration and review guarantees, and weaker root/generated equivalents.
  - Copier copy/update continues to preserve project-owned AGENTS and routing overrides while publishing the shortened managed entrypoint and its normative destinations.
completion_witness_map:
  - {"condition_sha256":"sha256:4d204ff42e60ceacdbfbcb72a366437157972a10d609932b43c07ae89bdb71b8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a4ed201fe54367d084f0b61f72e963ccabc15b91e823cdea85994bb704fe1d86","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:6a7a800410d7588bcdd2aaed39ed83b0ea5dc9c8ed56d65409a3461ee1bd519a","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:5f903e5accff79c6be528b9830558f8223fea6cf5697fc7069e4b10ebce946aa","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - references/template-development.md
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/validation_tools/plan.py
  - tests/fixtures/agent-policy-routing/scenarios.json
  - tests/fixtures/agent-policy-routing/evaluation-protocol.md
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - tests/test-validation-tools.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Relocate only duplicated procedural detail and deterministically preserve its obligation, direct-read task reachability, and root/generated equivalence before reducing AGENTS size.
  - Reduce root and generated managed AGENTS by at least 1000 bytes each from their activation baseline without increasing required source bytes for the fixed simple-task static scenario.
  - Publish the routed managed policy without overwriting any project-owned entrypoint or routing customization during Copier updates.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:cc6bce3e47adc6d2458e09f159030544802ad0ec726fe292435ae3be3854d8b0","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:5cbd7c2aa9e0f2b15125144b977e87d22d3c86c7ea670d21ffe9897bf721d623","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:eedc1ae9fbb9927be2abdfc1df2bed0ac7b3269afb1e9770c329045f50e7f5d1","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - Obtain explicit owner approval of this class C design before promotion or implementation; creating this backlog plan does not supply that approval.
  - Complete plans 272, 273, and 274 first and use their checked policy as the baseline; do not restore their superseded wording during this relocation.
  - Use bounded parent implementation and independent review because instruction routing and validation authority change.
  - Do not reduce an instruction merely because it is long; preserve every normative requirement verbatim except mechanical path/context adjustments before editing entrypoint pointers.
  - Keep direct reads mandatory; no compressed summary, generated index excerpt, or helper paraphrase substitutes for the governing policy.
  - Do not split or redesign ledger schemas, guardian protocols, review budgets, model routing, skills, or lifecycle implementations.
  - Keep fixed routing fixtures and critical requirements unchanged during wording adjustment; scenarios.json contains only median and edge cases, never the held-out evaluation input.
  - Before wording changes, an independent evaluator prepares and SHA-256-seals the held-out case in a parent-owned local artifact outside write_scope; record its digest but withhold the case from the implementer until the final frozen candidate is evaluated.
  - evaluation-protocol.md specifies this boundary but never embeds the held-out case; a changed case digest or use of its outcome for further tuning invalidates that evaluation.
  - Replace the duplicated guardian instruction with a mandatory route no longer than 300 UTF-8 bytes in each managed entrypoint; retain the full original rule in the declared normative destination.
  - Record independent scenario evaluation separately from deterministic route checks; static success is not evidence of agent productivity or empirical semantic success.
  - If a critical requirement fails or the independent review budget is exhausted, stop under the existing owner-decision policy rather than weakening requirements or repeatedly tuning.
checked_summary_ja: 起動時の AGENTS.md から重複する詳細手順を規範文書へ移し、作業別の直接参照と安全条件の検査を残す。

## Decisions

- 対象は、起動時に読む AGENTS.md の詳細規則とタスク別に直接読む規範文書の対応である。
- 短縮する対象は、root と生成側の管理対象 AGENTS に重複している移行手順と実行管理手順である。
- 常時必要な権限境界、停止条件、参照先の選び方は入口に残す。
- 各詳細規則は既存の規範文書を正本にし、同じ規則の新しい第三のコピーを作らない。
- 計画の受入、停止、完了証拠は root と生成側の SPEC_PLAN_WORKFLOW.md に置く。
- runner の操作、実行台帳、レビューセッションの手順は root の references/orchestration.md と生成側の SPEC_ORCHESTRATION.md に置く。
- Copier 移行時の guardian と更新証拠の手順は root の references/template-development.md と生成側の SPEC_COPIER_ADOPTION.md に置く。
- 資格情報と外部作用の共通禁止事項は、root と生成側の SPEC_SECURITY.md を正本として維持する。
- 通常の小変更、検証失敗後の停止、Copier 移行を固定シナリオにする。
- 調整に使わないシナリオには、別セッションでの再開とレビュー回数上限を用いる。
- 規則の欠落、圧縮物による規範代替、権限逸脱、停止無視を critical な失敗として扱う。
- 削減量は UTF-8 バイト数として記録し、token 数や応答時間の削減と同一視しない。

## Tasks

- [ ] Freeze the moved-requirement inventory, canonical destinations, activation-baseline byte counts, fixed median/edge scenarios, and critical requirements; have an independent evaluator seal the separate held-out input before changing wording.
- [ ] Move detailed rules to the existing normative destinations and add mandatory task routes; preserve semantic root/template alignment.
- [ ] Replace the duplicated entrypoint text with direct routing instructions while retaining the always-needed safety core.
- [ ] Update marker and alignment tests to inspect the actual normative destinations and route reachability, with negative tests for every lost obligation class and missing destination.
- [ ] Add baseline byte and static read-set checks to check-root-agent-policy.py and its existing test entrypoint; do not read raw logs or call models in these deterministic checks.
- [ ] Run one fresh independent scenario evaluation and, if an allowed revision is necessary, one fresh reevaluation; retain ambiguity and assumption reports locally and check the held-out case without further tuning.
- [ ] Run focused validation, complete independent acceptance review within the existing budget, and run authoritative validation once.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.
