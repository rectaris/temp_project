# Render plans from checked structured input

status: checked
primary_invariant: One bounded structured input is checked before writing, exposes the exact correspondence from each accepted requirement through write paths and completion predicates to claimed witness behavior and command, and byte-binds the plan and lifecycle-index update rendered from it.
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"The generated create-plan.sh already collects purpose, exact write paths, feasibility evidence, completion text, and witness commands before calling lint-plan-docs.py to derive admission JSON and allocate an id."}
  - {"kind":"existing_mechanism","evidence":"Root and generated admission validators already derive and check completion and acceptance SHA-256 values, exact focused-command membership, context paths, and repository-changing write scope."}
  - {"kind":"existing_mechanism","evidence":"Generated planlib.py already owns lifecycle locking and canonical active-index updates, while root check-root-agent-policy.py provides the root plan schema and admission checks needed after rendering."}
completion_conditions:
  - A bounded structured input identifies each accepted requirement and its exact write paths, completion conditions, acceptance items, claimed witness behavior, and declared command; pre-write output shows every correspondence and derived digest without omission or duplication.
  - The write operation rereads the exact input bytes, requires the digest returned by pre-write checking, rejects a changed input, invalid or missing mapping, unsafe path, occupied target, or invalid current index, and leaves no plan or index change on failure.
  - Root and generated-project entrypoints render their respective complete plan manifests from the checked input, preserve the existing generated command interface, and update the active index only through the canonical grammar and validation boundary established by plan 281.
  - Fixed ordinary, multi-plan, malformed-index, and condition-to-witness mismatch scenarios plus one separately identified holdout preserve all required conditions, expose semantic claims for review, and record structural false acceptance, false rejection, retries, and human decisions only when observed.
  - Root and installable generated files, operational guidance, inventories, parity checks, and smoke fixtures stay aligned without adding another authoritative plan record.
completion_witness_map:
  - {"condition_sha256":"sha256:05891bd60195772a1b5652b0bc80816c06e7525d0de2131cee72307eb76909ab","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:e23368945e46e52a265f0d060805c777f48ec99c7857216bc20328d7f4669bee","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f2b6edec5a7d9cfd970b5af759bd199a727ac539d31300fda2a621ee2e9d8630","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f43e2b453f9b6d7f083df2fc5b7cd475b4a22f149b9e75972f67e0230289a783","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2d37e7df0d0a35902063414c2bd33f28992f441453db6744e37ee3678386bfcf","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/create-root-plan.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - template/.project-agent-workflow/scripts/create-plan.sh
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/validation_tools/plan_authoring.py
  - tests/test-validation-tools.py
  - tests/fixtures/plan-authoring/cases.json
  - tests/fixtures/plan-authoring/holdout.json
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/check-root-agent-policy.py
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/support.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/plan_validation_commands.py --self-test
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Provide root and generated-project commands that show the complete requirement-to-scope-to-condition-to-witness correspondence before writing and render the complete plan from those exact checked bytes.
  - Reject changed input, broken mappings, unsafe paths, target collisions, and invalid current indexes before mutation, with atomic preservation of every pre-existing repository file.
  - Exercise the fixed ordinary, multi-plan, malformed-index, mismatch, and holdout cases while keeping semantic witness judgment visible to independent review and recording only observed outcomes.
  - Keep the root and generated authoring behavior and install inventory aligned without replacing plan files or lifecycle indexes as authority.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f88f1d55c57ec840d88709806a9344bed8a20e29387ebe2642d68df8c79a8fef","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:912c441e3e3c6bcf39f29cc9d47fdb8a8d87641be6d0a9deeedfb353008cf363","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:6c77303b4b14107e6df826f369cf9666fff14d090944bb7984ddae17fe4ed504","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:01ab65e5cc1b956d8bd3337cf3a301d4a45ee579e46913e9a4f32a7ef6e7cdc0","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Do not activate or implement this plan until plan 281 is checked. Resolve that checked implementation by id at activation and use its strict parser for every active-index read and write.
  - Treat the input as a bounded local authoring source, not a new repository authority. The rendered plan remains the implementation instruction and the existing lifecycle index remains the lifecycle record; do not commit routine input or preview files.
  - Accept one UTF-8 JSON object no larger than 256 KiB, reject duplicate keys and control characters, limit every admission list to its existing policy maximum, and reject absolute, parent-traversing, symlinked, or overlapping write/context paths.
  - Give requirements, paths, completion conditions, acceptance items, and witness claims stable input-local identifiers. Require explicit references and exact one-time coverage, then derive all manifest hashes rather than accepting caller-supplied condition or acceptance digests.
  - The check operation prints the exact input SHA-256 and a bounded ordered report of each requirement, its write paths, completion and acceptance text, witness claim, and command. It performs no repository write and does not claim semantic coverage.
  - The write operation requires the expected input SHA-256, rereads and revalidates the bytes under the existing lifecycle lock, refuses a stale digest or changed repository prerequisite, then atomically creates the plan and, for active plans, updates the canonical index. Backlog creation must not edit plan.md.
  - Preserve the existing generated create-plan.sh arguments as a compatibility path. Convert them to the same checked internal representation; do not maintain a second renderer or relax fields left as explicit authoring placeholders by that legacy interface.
  - The root command renders this repository's full plan schema, while the generated command renders the generated-project schema. Share validation and mapping rules where their policies match, but do not copy root-only project facts into generated plans.
  - Deterministic validation may prove bounds, references, derived hashes, output stability, atomicity, and scenario bookkeeping. It must not infer that a command semantically proves a condition from command membership or a caller-authored claim.
  - In independent review, examine the requirement and witness text shown for the mismatch case and one separately identified holdout after implementation choices and ordinary fixtures are fixed. Record observed required-condition loss, structural false acceptance or rejection, retries, human questions, and elapsed time only when the run supplies them; do not claim a speedup.
  - Keep this plan independent of plan 277's read-only resource summary. That plan may later display existing observations but is not a prerequisite and does not supply acceptance evidence here.
checked_summary_ja: 要件・変更先・完了条件・検査内容の対応を先に確認し、確認した同じ入力から計画と一覧更新を生成する。

## Decisions

- The concrete target is one bounded structured input whose validated requirement-to-scope-to-condition-to-witness correspondence is rendered into a plan file and its lifecycle index update.
- Use one read-only check followed by one digest-bound write; do not add an interactive approval service or durable shadow manifest.
- Derive condition and acceptance hashes in the renderer and expose claimed witness behavior for parent review.
- Preserve the existing generated command interface and add a usable root authoring command for this repository's plan schema.
- Keep semantic witness coverage under grounded parent and independent review rather than treating command existence as proof.

## Tasks

- [x] Freeze bounded input, preview, and write fixtures before implementation, including the separately identified holdout.
- [x] Add shared validation and mapping code, the root entrypoint, and the generated entrypoint compatibility path.
- [x] Implement exact-byte digest binding, safe target allocation, canonical rendering, and atomic plan/index writes after all checks pass.
- [x] Add fixed scenario tests that distinguish structural rejection from semantic review and preserve every observed result field without invented measurements.
- [x] Register new installable files and root/generated parity, update operational policy, and exercise both entrypoints in smoke fixtures.
- [x] Run focused validation, obtain independent review of the ordinary and holdout outputs, and run the unchanged authoritative suites once for an acceptable candidate.

## Validation Notes

- Planning baseline: `751b6b9d522ceaea727fd92be0ee81b816fac502` in `temp_project`.
- Owner direction: 「提案の方針でプランを docs/plan/backlog に作成せよ。」 This approves the selected design for backlog authoring; this turn does not activate or implement it.
- Plan 281 closes the fail-open index path first. This plan must use that checked behavior rather than duplicate or bypass it.
- Plan 275 routes detailed policy and Plan 277 summarizes already-observed resources. Neither supplies this checked authoring path or its validation.
- Feasibility evidence is based on existing source mechanisms. It is not a claim that the future renderer, scenario results, or completion witnesses already pass.
- No speed, token, retry, or human-effort improvement is claimed without a matching observation.
- Plan-authoring validation passed: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` exited 0. Smoke exercised generated-project cases; its optional GitHub Actions lint was skipped because `actionlint` was unavailable.
- Root admission, witness-digest, validation-command, context-path, and whitespace checks passed. These results validate this backlog document and the existing repository, not the future renderer or scenario outcomes.
- Implementation baseline: `b35ba58` in `temp_project`, which activated this plan and its index row as a separate commit.
- Owner direction for implementation: 「docs/plan/backlog/282-render-plans-from-checked-authoring-input.md について実装作業をせよ。」
- The shared library `plan_authoring.py` is installed byte-identically at `scripts/project_workflow/plan_authoring.py` and `template/.project-agent-workflow/scripts/plan_authoring.py`, and `scripts/check-copier-template.py` now enforces that identity together with the shared active-index grammar and admission constants.
- The legacy generated interface is a conversion, not a second renderer. The rendered plan file and index bytes were compared against the pre-change `create-plan.sh` for the same arguments and were identical.
- Command-grammar checking applies to the declared `validation` list only. Witness commands stay caller text, so the legacy interface keeps accepting the project-specific witnesses it always accepted.
- The holdout fixture predicted the correct decision for every case on first run. One case predicted the wrong rejection wording; the observed message was recorded in `observed_outcomes` and the recorded substring was corrected, and the checker was not changed to fit the prediction.
- Deterministic checking never infers semantics: a test asserts that two inputs differing only in claim wording produce the same structural report, and the report states that boundary in every run.
- Declared `write_scope` was incomplete for two mechanically entailed registrations, and both were changed: `tests/validation_tools/support.py` holds the module-path constants that every validation-tool domain imports from, and `tests/fixtures/orchestration/copier-update-source-inventory.txt` is the single inventory the Copier update fixture copies and stages from, so a new installable file that is absent from it is not part of the update the fixture proves. Neither change alters product behavior, and no other path outside the declared scope was written.
- Independent review (read-only helper, no write scope) reported four Medium findings against the first candidate, and one parent-direct remediation round cleared all of them. Acceptance stayed with the main session.
  - The authoring interface was a caller-supplied input field, so a hand-written input could declare `legacy_arguments` and unlock the placeholder relaxations. The field was removed from the input schema and the interface became a parameter of the conversion (`--authoring-interface`), refused for the root profile.
  - Declared `write_scope`, `context_files`, and `target_json` paths were not symlink-checked, so a declared path and the written path could differ. They are now refused at both check and write time.
  - The conversion narrowed three previously accepted argument invocations. The plan title is now stripped and bounded at 400 bytes instead of rejected, and the two remaining narrowings (absolute or repeated `--write-scope` values) are kept as defect fixes and recorded in both `SPEC_PLAN_WORKFLOW.md` files.
  - A failing plan-file write left a truncated file behind, because only the index write had a rollback. The plan file is now removed when its own write fails.
  - Two smaller items were also fixed: a JSON surrogate escape raised an uncaught `UnicodeEncodeError` instead of an authoring error, and no test covered the plan's multi-plan scenario. Both now have tests.
- The rereview of the remediated candidate reported one Medium and one Low finding, and a second parent-direct round cleared both. The reviewer then confirmed both closed with no new defect.
  - The legacy title relaxation had been applied to `summary` but not to `summary_ja`, which rejected Japanese titles the argument interface used to accept. Both titles now share one `title()` helper, so no asymmetry remains.
  - The root entrypoint only defaulted its profile, so it still accepted `--profile generated --authoring-interface legacy_arguments`. An entrypoint that declares a profile is now bound to it, and the root entrypoint carries no interface option at all.
- Legacy byte compatibility was re-verified after each remediation round: the plan file and index bytes for the same arguments remain identical to the pre-change `create-plan.sh`, including for the Japanese-title invocations that the first remediation had regressed.
- The digest binds the input bytes and not the interface, so `check` and `write` can be given different interfaces for the same bytes. This is not an escalation: every interface effect is a relaxation whose rendering coincides on the accepted intersection, a legacy-only input has no successful structured report to display, and the digest was never an authorization token. The report discloses the interface it used.
- Implementation validation passed once for the accepted candidate: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` both exited 0. Smoke's optional GitHub Actions lint was skipped again because `actionlint` was unavailable.
- Helper usage: one read-only `code-review` helper with no write scope produced the review, rereview, and confirmation. Its output was advisory; every change, the validation acceptance, and this record were made by the main session.
- No speed, token, retry, or human-effort improvement is claimed; no such measurement was taken.
