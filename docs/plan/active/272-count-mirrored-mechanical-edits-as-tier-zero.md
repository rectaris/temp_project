# Count exact mirrored mechanical edits as Tier 0

status: in_progress
primary_invariant: A single mechanical edit and its exact root/template counterpart may use Tier 0 only when existing validation, authority, reversibility, and semantic scope remain unchanged.
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
  - {"kind":"existing_mechanism","evidence":"AGENTS.md requires root policy/tooling changes to be mirrored, while SPEC_PLAN_WORKFLOW.md Implementation Tiers currently limits Tier 0 to one physical file."}
  - {"kind":"existing_mechanism","evidence":"scripts/check-copier-template.py require_plan_workflow_alignment already compares the relevant policy sections after the mechanical generated-path rewrite."}
completion_conditions:
  - Tier 0 permits one reversible mechanical change in one file or one exact root/template pair, but excludes unrelated edits, new behavior, and changes to policy meaning or validation and security authority.
  - Root and generated Implementation Tiers remain aligned and all pre-existing validation and escalation requirements remain in force.
completion_witness_map:
  - {"condition_sha256":"sha256:4e5cef489494ee85bdea7cc22e2f6cd7d0c4222498022996535df1e67c31f226","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f5c1e9dc524d8b3c4f72f71ec319d4f7b4cb8bb1705a27b954493bb39754c4d5","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/check-root-agent-policy.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/check-copier-template.py
  - tests/test-validation-tools.py
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
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Require existing validation and an unchanged semantic and authority boundary for both files before classifying a mirrored mechanical edit as Tier 0; every counterexample escalates to the existing higher tier.
  - Keep the root and generated tier policy mechanically aligned without weakening their current safety or validation requirements.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8ad776434b12f4334930fef5edd38caa2d107568bb923a8e68340786fe1756f8","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:ce8694ae4294f3cc1eeea8d9ef3a26e97a13e698cae0a2becfe5dcfc9b308622","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - This policy-classification change is Tier 2; do not use the proposed Tier 0 exception to implement this plan.
  - Use bounded parent implementation because the scope includes policy and validation authority; helpers remain read-only.
  - Do not enlarge the existing generic one-file exception or interpret any same-topic multi-file change as a mirrored pair.
  - Keep scripts/check-copier-template.py and its existing pair-alignment checks unchanged; add the root regression to the existing validation-tools entrypoint.
checked_summary_ja: 同じ機械的編集を反映する root と template の一組を、権限と意味を変えない場合に限って Tier 0 で扱えるようにする。

## Decisions

- 対象は、root と template の対応する二つのファイルに同じ機械的編集を適用したときの Tier 0 適格性である。
- 変更前の指摘は、root/template の同期義務と Tier 0 の物理ファイル数制限が衝突することである。
- 例外は、一つの既存対応ペアへ同じ機械的編集を行う場合だけに限定する。
- 既存の対応関係と決定的なパス書換を証拠にし、新しく作る対応表や人による同一性の主張だけでは認めない。
- 誤字、コメント、意味を変えない書式の修正を対象例とする。
- 挙動の変更、二つの独立した修正、生成専用分岐の変更、検証定義の変更、規則の意味の変更は例外から除外する。
- 本プランは将来の分類規則を変更するものであり、現在の実装 Tier を引き下げない。

## Tasks

- [ ] Record one qualifying mirrored typo example and negative examples for two independent edits, an asymmetric change, a behavior change, and a validation-authority change.
- [ ] Update the two aligned Implementation Tiers sections with the exact eligibility conditions and the existing escalation rule.
- [ ] Extend the root policy check and PlanValidationCommandsTest fixtures to require the exception and its exclusions; prove that deleting an exclusion makes the regression fail.
- [ ] Run focused validation, obtain independent read-only review, then run the unchanged authoritative suite once for the acceptable candidate.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.
