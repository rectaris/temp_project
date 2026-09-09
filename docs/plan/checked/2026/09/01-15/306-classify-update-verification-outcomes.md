# Give every verify-copier-update reason code one committed owner and next action, resolved by a bundled command instead of by agent prose

status: checked
primary_invariant: Every reason code the verification helper can emit resolves to exactly one committed owner and next action, and a reason code the table does not classify stops the reporting agent instead of receiving a guessed owner.
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
  - {"evidence":"The helper at .codex/skills/verify-copier-update/scripts/verify-copier-update.py already writes one machine-readable verification-manifest.json carrying a result and a reason_code, and already exits 0, 1 or 2 for verified, rejected and blocked, so the outcome is already a value and only its interpretation is still prose.","kind":"existing_mechanism"}
  - {"evidence":"Propagating the literal arguments that reach the helper's stop() reason-code position through its own syntax tree enumerates exactly 274 reason codes, so the table's completeness can be rechecked mechanically rather than asserted.","kind":"mechanical_transformation"}
  - {"evidence":"scripts/project_workflow/copier_inventory.py already registers the four verify-copier-update files in the root copy and the template copy, and scripts/check-copier-template.py already enforces that the two copies stay identical, so new skill files inherit the existing mirroring guarantee.","kind":"existing_mechanism"}
completion_conditions:
  - The committed triage table classifies every reason code the helper can emit and declares no entry the helper never emits, checked by re-deriving the code space from the helper itself.
  - The bundled resolver turns one verification manifest into exactly one owner and one next action, and refuses a manifest whose result and reason code disagree.
  - A reason code the table does not classify exits non-zero and names itself, so a reporting agent cannot absorb it into a guessed owner.
  - The template copy of the table, the resolver and the coverage check is byte-identical to the root copy and is registered in the Copier inventory, so a generated project resolves outcomes the same way this repository does.
completion_witness_map:
  - {"condition_sha256":"sha256:d4133535b7b37ce4f34e21de3a4b5e49781678acd55c5a1e02563e347612afb7","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:64cf904bf8fdf0c5ccf14ce41ead3a6174d3d4627c688590f03a64e761484142","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:6d438b9348022a414f1d8bdb15f78417960fb94bf55f23fc1f633e4dd8a6c23b","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:9f771e96a013ed7dff6b29ff67bcf3f7d13f828ec4d9088d924b58854d939c4c","witness":"python3 tests/test-verify-copier-update.py"}
write_scope:
  - .codex/skills/verify-copier-update/references/update-triage.yaml
  - .codex/skills/verify-copier-update/scripts/triage-copier-update.py
  - .codex/skills/verify-copier-update/scripts/check-triage-coverage.py
  - .codex/skills/verify-copier-update/SKILL.md
  - template/.project-agent-workflow/skills/verify-copier-update/references/update-triage.yaml
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/triage-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/check-triage-coverage.py
  - template/.project-agent-workflow/skills/verify-copier-update/SKILL.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/lint-project-workflow.sh
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/test-verify-copier-update.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - .codex/skills/verify-copier-update/references/verification-contract.md
  - scripts/check-copier-template.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - references/validation.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A downstream agent that runs the verification helper obtains its owner and next action from committed data rather than from its own reasoning, and an outcome the data does not cover stops it rather than producing an invented answer.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:8ca911f177989ea05579337bf390ef089ef1ddcd93d71c7b57a372f2c07faa86","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
checked_summary_ja: verify-copier-update が返す全理由コードに、責任主体と次の行動を委譲不能な表として持たせ、同梱コマンドで一意に解決する

## Decisions

- Record the owner and the next action in a committed table rather than in skill prose, because a table is the only form in which the repository can prove that every outcome the helper produces has an answer.
- Keep an owner value of undetermined for the outcomes a reason code genuinely cannot separate, and give those entries a bounded evidence step, rather than forcing a single owner and teaching downstream agents to report a guess as a fact.
- Re-derive the reason-code space from the helper's own syntax tree in the coverage check rather than maintaining a second hand-written list, so the table cannot drift when a new stop path is added.
- Propagate every parameter in that derivation rather than a named subset, because the helper forwards caller literals into the reason-code position through several helpers and a named subset silently missed ten codes.
- Fail the coverage check on an entry the helper never emits as well as on a code the table never classifies, so a removed check leaves no stale advice behind.
- Read the table with a bundled reader when the YAML library is absent, because a downstream agent runs this skill on a machine this repository does not provision and a missing library must not turn a decidable outcome into an unresolved one.
- Resolve a code by trying the longest declared subject first and falling back to a shorter one, so a state-file subject wins over the repository subject that is its prefix without hiding the codes the repository subject still owns.
- Exit non-zero on an unclassified code rather than reporting it with a default owner, because absorbing an unknown outcome into a plausible answer is the failure the table exists to remove.
- Refuse a manifest whose result and reason code contradict the table rather than trusting either, because that disagreement means the manifest and the table describe different helper versions.

## Tasks

- [x] Record every reason code the helper can emit in a committed triage table with one owner, one next action and one retry answer.
- [x] Add a bundled resolver that turns one verification manifest into that single answer and stops on an unclassified code.
- [x] Add a coverage check that re-derives the code space from the helper and fails when the table and the helper disagree.
- [x] Mirror the new files into the template copy, register them in the Copier inventory, and run the coverage check from the repository lint.
- [x] Cover the table, the resolver and the mirroring with deterministic tests, then run the authoritative suite once.

## Validation Notes

独立レビューは、網羅検査が `VerificationStop` の直接構築を数え落として理由コード 4 件を取りこぼすこと、`_src_path` 由来の 4 件と `update_wrapper_invalid` の責任主体が誤っていること、YAML 代替リーダが未対応構文を黙って別解釈することを指摘した。いずれも受け入れて修正し、退行試験を加えた。

`python3 tests/test-verify-copier-update.py` を実行し、49 件すべてが通過した。理由コードの網羅検査は 278 件を分類済みと報告した。

`scripts/lint-project-workflow.sh` を実行し、245 件の検査が通過した。出力中の `root agent policy check failed:` 行は、既存の否定系テストが意図的に出力するものである。

`REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` は、生成物の目録比較が HEAD のクローンを読むため、新規ファイルをコミットしたうえで一度だけ実行した。
