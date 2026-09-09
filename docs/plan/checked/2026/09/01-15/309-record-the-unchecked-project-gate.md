# Let a project whose own gate cannot run in a fresh clone be verified, and record in the result that its gate was not run

status: checked
primary_invariant: A verification that ran no project validation command reports a reason code that says so, and a caller who says nothing about the project's gate is still refused.
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
  - {"evidence":"The helper stops with validation_missing when no project validation command is passed. Every gate the three downstream projects declare needs installed dependencies, and a verification runs inside a fresh clone, so all three stop before any update and no release can be checked against them.","kind":"reproduced_defect"}
  - {"evidence":"Verifying supportcard-status showed the generated change-aware validation rejecting the updated project, so the template-side check alone already catches a real template defect and is worth running for a project that has no gate of its own.","kind":"reproduced_defect"}
  - {"evidence":"Every outcome already carries one reason code that the committed triage table resolves to one owner and next action, and check-triage-coverage.py refuses an unclassified code, so a second verified code needs no new reporting path.","kind":"existing_mechanism"}
completion_conditions:
  - A verification that declares the project has no runnable gate completes, reports a verified result under a reason code that names the missing project validation, and records the declaration in the manifest.
  - A caller who passes no project validation command and makes no declaration is still stopped with validation_missing, and a caller who does both is stopped with a named conflict.
completion_witness_map:
  - {"condition_sha256":"sha256:ba8b24ac82cc912236f305d409977178ab0f43b1025736b2585543cf7d837527","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:7bca5b6da739268dd29d260bf285de4478eb58210ad0f561c6cd3e35d611c3a7","witness":"python3 tests/test-verify-copier-update.py"}
write_scope:
  - .codex/skills/verify-copier-update/scripts/verify-copier-update.py
  - .codex/skills/verify-copier-update/references/update-triage.yaml
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/references/update-triage.yaml
  - scripts/verify-downstream-baselines.py
  - tests/test-verify-copier-update.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/downstream-baselines.yaml
  - scripts/check-copier-template.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A reader of a verified result can tell whether the project's own gate was run, because an unrun gate carries its own reason code and its own next action rather than the ordinary verified one.
  - The aggregate runner declares the absence for a baseline that records no command, so a release candidate can be checked against every recorded downstream project instead of stopping on all of them.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b7c07ec5da7bdb734986fdf88b729883eb98cf45b1ca866e44e52438ccc62f51","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
  - {"acceptance_sha256":"sha256:dd2fa428fa61dd16c18de3cba8f0d51e18b8d064a4654d52e39077a840509277","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
checked_summary_ja: 自前の検査を素の複製で走らせられないプロジェクトも検証できるようにし、その検査を実施していないことを結果に残す

## Decisions

- Require the caller to state the absence rather than treating an empty command list as the statement, so a caller who simply forgot the gate is still refused and only a deliberate declaration reaches the weaker result.
- Report the declared absence as a second verified reason code rather than as a new result value, because the result vocabulary is what callers branch on and a third value would change every caller, while the reason code already carries the owner and the next action.
- Refuse a declaration passed together with a command instead of preferring one of them, because the caller stated two different things about the same project and neither reading is safe to assume.
- Keep the generated change-aware validation running for a declared absence, because it is the template's own gate and it already rejected a real update, so the weaker result still carries the check this repository owes.

## Tasks

- [x] Accept an explicit declaration that the project has no runnable gate, and refuse it together with a passed command.
- [x] Report a declared absence under its own verified reason code and record it in the manifest.
- [x] Classify the new codes in both triage tables and mirror the helper.
- [x] Declare the absence from the aggregate runner for a baseline that records no command.

## Validation Notes

`python3 tests/test-verify-copier-update.py` を実行し80件成功した。`scripts/lint-project-workflow.sh` を実行し通過した。`tests/smoke.sh` は commit 後に実行する。

独立レビュー（読み取り専用、gpt-5.6-sol）を1巡かけ、2件の指摘をいずれも受け入れて修正した。

1件目は重大だった。記録側で `validation_commands` の項目そのものを書き忘れた場合と、値を空にした場合を区別せず、どちらも「このプロジェクトに走らせられる検査はない」という宣言として扱っていた。宣言が意図的であることが安全性の根拠なので、書き忘れが弱い結果に到達できる時点で根拠が失われる。項目の存在と型を必須にし、明示した空の一覧だけを宣言として扱う。

2件目は、検査を実施していない結果に所有者を置かなかった点である。誰かが後で走らせなければならないのに `owner: none` としていた。結果表に `residual_obligation` を導入し、やり残しを持つ符号は所有者を持たねばならないことと、その次の行動を「検証済み」の場合でも表示することを定めた。

修正後の再レビューは行っていない。
