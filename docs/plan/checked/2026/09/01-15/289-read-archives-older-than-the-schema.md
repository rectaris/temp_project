# Let a checked archive written before a manifest field existed stay readable instead of demanding metadata its vintage never wrote

status: checked
primary_invariant: A legacy checked record is judged only on the fields it actually carries, and every field it does carry is judged exactly as before.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"In a served project all 277 checked archives carry task_type, target_files, expected_output, required_specs, validation, and checked_summary_ja; none carries status or acceptance, and only 49 carry the review triad. The generated lint stops at the first archive with 'missing field: status:'.","kind":"reproduced_defect"}
  - {"evidence":"lint_manifest already branches on is_legacy_checked to accept the removed field names, then requires LEGACY_REQUIRED_FIELDS, which names status, review_class, human_design_required, human_approval_status, and acceptance. That vintage never wrote them, so the tolerance branch cannot be satisfied.","kind":"reproduced_defect"}
  - {"evidence":"Judging those five fields only when the archive carries them makes the generated change-aware validation of that project pass all 25 selected commands, with no other change to the archive.","kind":"bounded_prototype"}
completion_conditions:
  - A legacy checked record missing status, review_class, human_design_required, human_approval_status, or acceptance is accepted, and its status is read as checked from its location.
  - A legacy checked record that writes any of those five fields with a value outside its allowed set is still refused with the same message.
completion_witness_map:
  - {"condition_sha256":"sha256:ee2d2ffe371dd9b77d4d61add051e98648dffdca4f9b27359f020bda4ca262f3","witness":"python3 -m unittest tests.validation_tools.plan"}
  - {"condition_sha256":"sha256:0e66f22dae27f7f3e09b1471f3e2d10a3ff62476f3f74bbb8021395f94135033","witness":"python3 -m unittest tests.validation_tools.plan"}
write_scope:
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/downstream-baselines.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 -m unittest tests.validation_tools.plan
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A checked archive older than the current manifest schema is read without demanding the fields its vintage never wrote, and any such field it does write is judged exactly as before.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:9d3ac9156bddb0918eda0bc950b3b16a33ffbf5bdc89af991d9979536dd6f657","stage":"focused","witness":"python3 -m unittest tests.validation_tools.plan"}
checked_summary_ja: マニフェストに項目が加わる前に書かれた確認済みアーカイブを、その世代が書きようのないメタデータを要求せずに読めるようにする

## Decisions

- Judge each of the five late-arriving manifest fields only when the archived record carries it, rather than exempting archives from manifest lint altogether, because the 49 records that do carry review metadata must keep being checked.
- Read an absent status as checked from the record's location under docs/plan/checked/, because the directory already states the fact that the field would repeat.
- Read the predecessor gate through the same location-derived status, because a plan that names a pre-vintage archive as its predecessor would otherwise be refused for a field that archive never wrote.
- Fix this in the template instead of writing the missing fields into 277 archived records, because a completed plan's review class and approval history cannot be reconstructed after the fact and writing a guess would fabricate history.

## Tasks

- [x] Judge status, review_class, human_design_required, human_approval_status, and acceptance in a legacy checked record only when the record carries them, reading an absent status as checked.
- [x] Cover an archive older than those fields and an archive that writes one of them with a wrong value.

## Validation Notes

独立レビューを1巡受け、Medium指摘3件をすべて受理して修正した。修正後の再レビューは行っていない。

- 指摘1: 項目を宣言したうえで値を空にした記録が検証を素通りし、空の `status:` が `checked` と読まれていた。判定の有無を解析後の値の真偽ではなく、本文に `^項目名:` が現れるかどうかで決めるよう改め、宣言された項目は必須項目の組に残して空値を拒むようにした。
- 指摘2: review_class が C の記録に対する承認規則が `judges["human_approval_status"]` で囲われておらず、承認欄を持たない旧世代の記録が拒まれていた。同じ門の内側に入れた。
- 指摘3: `planlib.py` の後続計画検査2か所が `status: checked` の literal を要求していた。`archived_status()` を追加し、両方の呼び出し位置を置き換えた。この修正のために `planlib.py` を write_scope に移した。

検証結果:

- `python3 -m unittest tests.validation_tools.plan` — 83件成功。宣言済み空値5種と、status を持たないアーカイブを後続計画の先行として読む経路を追加で覆った。
- `scripts/lint-project-workflow.sh` — 通過。
- 実データ確認: 実際に277件の旧世代アーカイブを持つ配布先プロジェクトの作業用複製に、修正後の `lint-plan-docs.py` と `planlib.py` を写して `validate-changes.py` を実行し、終了コード0を得た。
