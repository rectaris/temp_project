# Treat an owner quotation recorded in the plan manifest as the standing continuation authorization at plan start

status: checked
primary_invariant: A plan's own standing_continuation_authorization line, holding the owner's verbatim words, is the only new source of a standing authorization; it is bound to the exact committed plan before the first formal review, and a plan without it, the four-review maximum and the fresh owner decision after the fourth review are unchanged.
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Plan 421 stopped for owner approval after formal reviews 1 and 2 on 2026-09-27, although the owner expected plan 420's standing rule to apply, because no standing record was registered before its first formal review and registration is refused afterwards.","kind":"reproduced_defect"}
  - {"evidence":"register_standing_authorization in plan-execution-state.py binds a bounded owner quotation to the plan path and digest, source head, epoch-0 genesis and continuation registry, and refuses registration once any parent_review exists.","kind":"existing_mechanism"}
  - {"evidence":"require_repository_baseline already reads the committed plan bytes under the plan-digest check and extracts the single primary_invariant line with a regex, so a second single-line manifest field can be read under the same binding.","kind":"existing_mechanism"}
  - {"evidence":"plan_authoring.py renders optional root profile scalars such as implementation_risk, and restructure-plan.py lists rebind-protected manifest fields in REBIND_PROTECTED_FIELDS; both files have byte-identical template copies.","kind":"existing_mechanism"}
completion_conditions:
  - standing-authorization takes the quotation from the committed plan's single standing_continuation_authorization line when it exists, refuses a blank, placeholder, duplicated or over-400-byte value and a differing --owner-authorization, and still requires --owner-authorization when the line is absent.
  - For an epoch-zero run whose committed plan declares standing_continuation_authorization, review refuses the first formal review before reviewer admission or any ledger effect until the standing record is registered, and a plan without the field keeps the existing review behavior.
  - A plan-sourced standing record derives and verifies the schema-1, schema-2 and schema-3 continuation authorizations exactly like an explicit one, and resolve-owner and owner-accept still refuse it and require fresh owner records.
  - create-root-plan.py and the generated authoring profile render an optional standing_continuation_authorization scalar, and refuse a blank, placeholder, multi-line or over-400-byte value.
  - Both restructure-plan.py copies treat standing_continuation_authorization as rebind-protected, so no rebind or activation record adds, removes or changes it.
  - AGENTS.md, orchestration guidance and the orchestrator skill state that the owner's verbatim words in standing_continuation_authorization count as the standing authorization at plan start and that an agent never writes the field from inference, and the root checker asserts this and refuses a malformed field in a live plan.
  - Both Review-Finding Budgets sections describe the rule identically after the path rewrite, the plan-execution-state.py, plan_authoring.py and restructure-plan.py copies stay byte-identical, and the generated AGENTS body and orchestration copy state the same rule.
  - Backlog plans 422 and 423 declare standing_continuation_authorization with the owner's recorded words, and the root checker admits them.
completion_witness_map:
  - {"condition_sha256":"sha256:fe8b4e8634755733c3186582783b57affc30cc4dfef8bd82ce885011db3c6e0f","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:42a7d109f7ba40941a1c9c25ca5592b5030a509de52602c456a31e5d50d4ae00","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:ad79c66a61e916bb02ee562f3b6a8f3b9057376c5af333a20318c9cf44a38566","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:9356855c7ee0af4cb827fb26dd480f818aaff9d7e3c6679f9f58c2368ff45e85","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:ac2b76363bff95c675280f604e31f53702f0074daa359e0a18c3d783b6a3a808","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:633b930e1d2643246c58130ff2f09440108431c6b6d995ad8578c41cf4a9c13d","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:776d74aa6c7b2cd628b3b6dfe7316ba8120847c356a15d9608fea19cdb5855f0","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:96713dd5952ab500b3d7e12a5b93ff87c79990d4b8991bc073a6e8b9ce4dc85f","witness":"python3 scripts/check-root-agent-policy.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - tests/validation_tools/plan_authoring.py
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - template/.project-agent-workflow/scripts/planlib.py
  - AGENTS.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - CHANGELOG.md
  - docs/plan/backlog/422-provision-task-worktrees-with-the-locked-uv-environment.md
  - docs/plan/backlog/423-run-sandboxed-python-helpers-from-a-reachable-interpreter.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/16-31/420-record-standing-owner-continuation-up-to-four-reviews.md
  - docs/plan/checked/2026/09/16-31/421-route-writable-work-to-terra-after-spark-retirement.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - When the owner's approval is recorded in a plan's manifest, that plan runs through the fourth review's stop without asking the owner again, unless a stop is ineligible for continuation or is not a review-budget stop.
  - A plan without the field behaves exactly as before, every continuation still records a bound authorization, the four-review maximum is unchanged, and the stop after the fourth review still needs a fresh owner decision.
  - Root and generated policy, specification, authoring, restructuring and execution-state copies state and implement the same rule.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:bed7fcf1aa184f78ad6c1e9493a7658a013be4656537d0d93b677d6c831cd66a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:691fb1b5746c58383265fa9b9dd9b3c3f7fcba175b6e1c71dcc4e5daf65efd18","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:c26e5e53f03da8f50a18d8883341e142a7de626d661252a387be0cf3a367ef40","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 計画ファイルに記録したオーナーの承認の言葉を、開始時の続行の事前承認として扱う。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger, because this plan changes the source of owner authorization and the validation authority that checks it.
- Add one optional single-line manifest scalar, standing_continuation_authorization, in the root and generated plan profiles. Its value is the owner's verbatim words, at most 400 UTF-8 bytes; name their date and source in Validation Notes. An agent records it only from the owner's own words and never from inference or paraphrase.
- standing-authorization reads the committed plan under the existing plan-digest check. With the field, the quotation comes from the plan and a differing --owner-authorization is refused; without it, --owner-authorization stays required. The standing record schema and the derive, verify and continuation commands stay unchanged.
- Make review refuse the first formal review of an epoch-zero run whose committed plan declares the field until the standing record exists, before reviewer admission or any ledger effect. Do not add automatic registration to prepare-parent-direct.
- Rebind-protect the field in both restructure-plan.py copies, and validate its shape on live root plans in the root checker.
- Record the owner's 2026-09-27 words in backlog plans 422 and 423. Before this plan's first formal review, register its own standing authorization with the existing explicit command, quoting the same words from its Validation Notes.
- Never derive the schema-4 resolve-owner authorization or the owner-accept decision from a standing record, whatever its source; the four-review maximum is unchanged.

## Tasks

- [x] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, register the standing authorization with the owner's words quoted in Validation Notes, record the review-route check, and record the unchanged baseline results of the focused suites.
- [x] Implement plan-sourced registration and the first-review gate in both plan-execution-state.py copies, with cases for the field, its refusals, derivation for epochs 1 to 3 and the unchanged path without it.
- [x] Add the optional field to both authoring profiles and the rebind-protected set in both restructure-plan.py copies, with their cases.
- [x] State the rule in AGENTS.md, the generated AGENTS body, both Review-Finding Budgets sections, both orchestration copies, both orchestrator skills, both checkers and CHANGELOG.md, and add the field to backlog plans 422 and 423.
- [x] Record a passing adversarial preflight, obtain independent review through a fresh read-only Codex reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner statement on 2026-09-27, after plan 421 asked twice for continuation approval: 「420 プランはすでに実装されているため、 こちらに 4回レビューまで承認を求めなくともよいようにしていたはずだが」. The owner then chose option 2, recording the owner's approval in the plan file, with 「2 の計画で作成する。」.
- Run this plan before plan 422, so plans 422 and 423 start with their recorded approval.
- Parent-direct implementation was prepared against source `208a6c8852dbf2fc85f9feca89f2d59ec77057a5`. Before any review, the existing explicit `standing-authorization` command registered the owner statement quoted above (the first quotation) as this plan's standing authorization. Each epoch recorded its own runtime-proven read-only route probe and exact-target adversarial preflight. No writable helper was used.
- Baseline: the execution-state (277), restructure (216), root policy and Copier template checks passed before product edits. `python3 tests/test-validation-tools.py` failed 15 Ruff-dependent lint cases under the plain system Python and passed (425) with the main checkout's pinned `.venv/bin` first on `PATH`; later runs used the same split (plan 422).
- Standing mode continued each eligible review-budget stop without a new owner message. Formal review 1 recorded High and Medium and stopped epoch 0: the ledger admitted placeholders such as `pending`, and trusted a field present only in uncommitted plan bytes. Derived schema-1 authorization, verified, `continue` opened epoch 1.
- Formal review 2 recorded one Medium and stopped epoch 1 with two findings: an uncommitted deletion of a committed field bypassed the gate, and a field-shaped body line was trusted although restructuring reads only the leading manifest. Derived schema-2 authorization, verified, `continue-final` opened epoch 2.
- Formal review 3 recorded one Medium and stopped epoch 2: a noncanonical key such as `standing_continuation_authorization : words` was ignored by the ledger and the root checker but read as the field by planlib and restructuring. Derived schema-3 authorization, verified, `continue-fourth-review` opened epoch 3.
- Formal review 4, in a fresh read-only Codex session, reported `REVIEW-VERDICT: none`. No owner resolution was needed; the cumulative four-review maximum was reached, not exceeded.
- The ledger, the root checker and plan authoring now share the admission placeholder vocabulary, also refusing dotted spellings such as `t.b.d.`. The field is read only from the source-head blob that the ledger digest binds. It is recognized as planlib and restructuring recognize keys, and only in its canonical spelling in the leading manifest. A throwaway harness checked that the four parsers agree across 3,150 spelling, placement and value variants.
- Regression proof: the new execution-state, authoring and restructure cases failed against the source baseline and pass now. The review-1 and review-2 regression cases also failed against the first implementation, and the review-3 spelling cases failed against the epoch-2 implementation. A mutated copy of the repository made both checkers fail: a duplicated field in plan 422 and a removed rule marker in the generated AGENTS body.
- Focused validation passed: `python3 tests/test-plan-execution-state.py` (282 tests), `python3 tests/test-validation-tools.py` (427 tests), `python3 tests/test-plan-restructure.py` (217 tests), `python3 scripts/check-root-agent-policy.py` and `python3 scripts/check-copier-template.py`. Authoritative `scripts/lint-project-workflow.sh` and `tests/smoke.sh` each ran once after the clearing review and passed. The completion and archive execution gates passed before lifecycle edits.
- Accepted implementation commit: `175ee65`. External ledgers, standing and derived authorizations, receipts, review evidence and validation output are retained under `~/.local/state/project-agent-workflow/plan-424-20260927/`. Link changes: none.
