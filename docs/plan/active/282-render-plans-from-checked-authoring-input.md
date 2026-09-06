# Render plans from checked structured input

status: in_progress
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

- [ ] Freeze bounded input, preview, and write fixtures before implementation, including the separately identified holdout.
- [ ] Add shared validation and mapping code, the root entrypoint, and the generated entrypoint compatibility path.
- [ ] Implement exact-byte digest binding, safe target allocation, canonical rendering, and atomic plan/index writes after all checks pass.
- [ ] Add fixed scenario tests that distinguish structural rejection from semantic review and preserve every observed result field without invented measurements.
- [ ] Register new installable files and root/generated parity, update operational policy, and exercise both entrypoints in smoke fixtures.
- [ ] Run focused validation, obtain independent review of the ordinary and holdout outputs, and run the unchanged authoritative suites once for an acceptable candidate.

## Validation Notes

- Planning baseline: `751b6b9d522ceaea727fd92be0ee81b816fac502` in `temp_project`.
- Owner direction: 「提案の方針でプランを docs/plan/backlog に作成せよ。」 This approves the selected design for backlog authoring; this turn does not activate or implement it.
- Plan 281 closes the fail-open index path first. This plan must use that checked behavior rather than duplicate or bypass it.
- Plan 275 routes detailed policy and Plan 277 summarizes already-observed resources. Neither supplies this checked authoring path or its validation.
- Feasibility evidence is based on existing source mechanisms. It is not a claim that the future renderer, scenario results, or completion witnesses already pass.
- No speed, token, retry, or human-effort improvement is claimed without a matching observation.
- Plan-authoring validation passed: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` exited 0. Smoke exercised generated-project cases; its optional GitHub Actions lint was skipped because `actionlint` was unavailable.
- Root admission, witness-digest, validation-command, context-path, and whitespace checks passed. These results validate this backlog document and the existing repository, not the future renderer or scenario outcomes.
