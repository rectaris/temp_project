# Generate isolated plan candidates and integrate them in order

status: replanned
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"run-sandboxed-plan-worker.py derive_worker_contract, verify_candidate_manifest and execute_validation_operation already bind exact candidate bytes and run parent-authorized commands in fresh credential-free network-isolated clones."}
  - {"kind":"bounded_prototype","evidence":"A disposable Git fixture committed A, applied the original C0-based B patch with git apply --check in a separate A-based clone, observed a textual conflict, and confirmed both committed A and the ordinary dirty checkout were unchanged."}
  - {"kind":"existing_mechanism","evidence":"Existing admitted-patch equality, current HEAD/plan checks, parent-direct review and accepted descendant-commit checks define the acceptance predicates that a grouped integration path must retain under fresh baseline identities."}
completion_conditions:
  - An explicitly admitted two-member group starts independent worker candidates in separate managed parent worktrees and existing disposable sandboxed clones, with exact member permits and no shared candidate writes or source publication authority.
  - When A is ready first, the parent validates and publishes A while B remains isolated; B is later assembled in a fresh clone of the A-containing target, with original evidence preserved and a new exact review/validation target.
  - Textual conflicts and automatically applicable semantic conflicts are resolved only within the current member scope and both members' frozen requirements; unresolved conflicts, missing A behavior, scope drift and incompatible requirements prevent publication.
  - Each final assembled candidate receives current-spec parent review, independent review within the inherited budget, focused validation and one authoritative suite; old-baseline success, diagnostic output and worker completion claims cannot satisfy those gates.
  - Publication is parent-only and serialized, verifies the exact expected target commit and clean checked-out target under the lease, and advances only the reviewed commit; target drift, dirty user work and ambiguous crash evidence preserve the target and refuse completion.
  - Baseline transfers, conflict edits and target drift preserve per-member budgets and stopped states; a formal validation failure records diagnosis_required before any further operation.
  - Only published member results become formally accepted or archived, and the group completes only after both publish; root and generated completion commands reject readiness artifacts and preserve normal plan-history transitions.
completion_witness_map:
  - {"condition_sha256":"sha256:19e329f7523708f26f8ad5095187ffa69c0ba8ea7839020094c4d52a59316fdf","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:9aab97c9d08aca9d912dbeebedd57084857d41be49527ad9faa7de389e45e9b2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:4107e103f0b141a19c0ac70464027f4efcde979ee5290809f508aa0999f789f2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:3c3032880a571e9e290c57652930cb64f414237483b48ff9ed87b9c89dc551f2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:245570d6e1dc1d237b06a72d31240d38f0737c52ab173fd05a8781ef8faeb385","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:de5dd4df74efac5c645235cf11fe0dc77d046a0b247d8c715e44559b61b507a0","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:d1c9f88e9a758ae36d1c25df4f49aa33155ae6e3b9ce78f0236ae3204a5ec255","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/run-parallel-plans.py
  - template/.project-agent-workflow/scripts/run-parallel-plans.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/parallel-plan-state.py
  - template/.project-agent-workflow/scripts/parallel-plan-state.py
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/test-sandboxed-plan-worker.py
  - tests/test-plan-execution-state.py
  - tests/validation_tools/plan.py
  - tests/validation_tools/generated.py
  - tests/root-plan-lifecycle.sh
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan_validation_commands.py
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/plan/active/278-create-resumable-parent-worktrees.md
  - docs/plan/active/279-bind-parallel-plan-execution-to-shared-authority.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - scripts/restructure-plan.py
  - docs/plan/backlog/276-run-bounded-parent-owned-candidate-preflight.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
predecessor_plans:
  - docs/plan/active/278-create-resumable-parent-worktrees.md
  - docs/plan/active/279-bind-parallel-plan-execution-to-shared-authority.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-plan-execution-state.py
  - python3 tests/test-validation-tools.py
  - tests/root-plan-lifecycle.sh
  - python3 scripts/check-copier-template.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Use the admitted group and isolated worker path to generate independent A/B candidates concurrently without allowing workers to modify shared branches, plans, validation definitions or other members' outputs.
  - Integrate the first ready member and then assemble the later member against the current target, resolving compatible textual and semantic conflicts while preserving both members' accepted requirements and source work.
  - Bind review and complete validation to the exact final assembled patch and current baseline; refuse stale evidence and publish only through an exclusive checked expected-target transition with bounded recovery.
  - Preserve the later member's cumulative correction/review budgets, reviewer registry and every existing stopped-state gate across baseline changes, conflict resolution and target races.
  - Tie formal member/group completion and lifecycle archival to verified publication while preserving default serial lifecycle behavior.
  - Preserve project-owned plans, group descriptions, configuration and history during an actual Copier update that installs the new commands and policies.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:ba288aa7fa923948ecb4f9b3f6872aac546ae266e2cc620574bf3f6920c26eca","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:f109d0c5c1584574f128c26b3d8f7532ace51a444a4105ccec7d83cd72221d00","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:2bc6d247a39029db6e21f7e0c338ceb489a24d9d3644dfab923318cd54442db2","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:e37655466fcce450f6032dff0ff7c7211203cdaf69d78320c1ee0a66e532220a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:3545d5300f7a1d1d7c7182dedc987ffc57cf28477d7c445075916d044da912d2","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:0254eda4cd7cc8218234057c448e5e87e1a49d2d4a242ca54c3d3df5c8b6e3f1","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"The required before-update, migration and after-update preservation is checked by the real isolated Copier transaction; no existing narrower command executes this complete update boundary. Static parity and focused lifecycle fixtures run first but cannot establish this end-to-end result."}
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/278-create-resumable-parent-worktrees.md
  - docs/plan/active/279-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/active/280-integrate-parallel-plan-candidates-in-order.md
replan_contract: docs/plan/replanned/contracts/278-complete-resumable-parent-worktrees.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/283-complete-resumable-parent-worktrees.md
  - docs/plan/active/284-bind-parallel-plan-execution-to-shared-authority.md
  - docs/plan/active/285-integrate-parallel-plan-candidates-in-order.md
inherited_acceptance_digests:
  - sha256:ba288aa7fa923948ecb4f9b3f6872aac546ae266e2cc620574bf3f6920c26eca
  - sha256:f109d0c5c1584574f128c26b3d8f7532ace51a444a4105ccec7d83cd72221d00
  - sha256:2bc6d247a39029db6e21f7e0c338ceb489a24d9d3644dfab923318cd54442db2
  - sha256:e37655466fcce450f6032dff0ff7c7211203cdaf69d78320c1ee0a66e532220a
  - sha256:3545d5300f7a1d1d7c7182dedc987ffc57cf28477d7c445075916d044da912d2
  - sha256:0254eda4cd7cc8218234057c448e5e87e1a49d2d4a242ca54c3d3df5c8b6e3f1
checked_summary_ja: A を先に取り込み、B を A 適用後のコードと別の作業場所で組み合わせて検証し、競合解消と回数制限を守って順番に取り込む。

## Decisions

- The parent combines a completed plan candidate with the current target commit in a disposable checkout, resolves compatible conflicts, validates the exact result, and serially publishes it only while the target remains unchanged.
- Candidate generation may be parallel; source publication and formal lifecycle transitions have one parent writer.
- A completed worker candidate is ready for parent consideration, not checked plan completion. The formal accepted result is the exact reviewed and validated commit actually published to the target.
- After A publishes, B uses a fresh A-containing baseline and fresh assembled-result evidence. Original B worker evidence remains immutable and B retains the same logical budget owner.
- Resolve conflicts outside the ordinary checkout. Preserve both requirements for routine resolution and stop for owner decisions when requirements or authorized boundaries must change.
- Keep initial group size and baseline transfer bounded to two members and one transfer per member. This delivers the requested A-then-B flow without an unbounded merge/review retry loop.

## Tasks

- [ ] Extend the runner's exact versioned contracts to accept only the group/member permit issued by 279, while retaining legacy verification and no worker source-write authority.
- [ ] Implement parent group dispatch through separate worktrees and existing worker clones, returning immutable readiness artifacts without invoking acceptance automatically.
- [ ] Implement the current-baseline assembly operation and distinct parent-produced evidence for unchanged application and in-scope adjusted results.
- [ ] Test that one substantive parent adjustment consumes the same single slot as worker correction, that either excludes the other, and that crash recovery or a mechanical no-edit transfer never resets the slot.
- [ ] Implement current-target review/validation and inherited budget checks, including diagnosis_required before any further action after authoritative failure.
- [ ] Implement serialized expected-target publication and bounded crash recovery, including safe handling of checked-out clean versus dirty targets.
- [ ] Test direct invocation of both root and generated complete/finalize commands before publication, after publication and after interrupted publication, preserving legacy behavior for ungrouped plans.
- [ ] Bind existing member completion/archive operations and group completion to verified published commits; preserve A when B stops and block duplicate finalization.
- [ ] Add deterministic end-to-end, negative, race and untuned holdout scenarios to the existing complete test entrypoints and preserve default serial behavior.
- [ ] Update aligned orchestration and lifecycle guidance, install inventory/parity, generated smoke and Copier update preservation fixtures.
- [ ] Review the exact implementation and invariants independently, run all declared focused commands, then the authoritative suites once for the otherwise acceptable result.

## Validation Notes

- Planning baseline: `56dd79a2461acd9880f27cf7c75f62a1dad877a5` in `temp_project`.
- Owner authorization: 「この方針でプランを docs/plan/active に作成せよ。」 The owner selected the preceding proposal and A/B conflict-resolution explanation; the accepted design is approved for this bounded plan. This turn creates plans only and does not execute their product changes.
- These are new plans, not a reconstruction of a stopped source, so no historical restructuring contract, acceptance set or owner-continuation record is fabricated or changed.
- Feasibility is bounded source inspection and, where named, a disposable Git prototype run during planning. It is not a claim that the new runtime behavior or future completion witnesses already pass.
- Full decision audit and planning prototype are local evidence under `.agent-artifacts/decision-audits/parallel-plan-worktrees/`; final decisions needed for execution are stated here.
- Plan-authoring validation passed: scripts/lint-project-workflow.sh and tests/smoke.sh (exit 0). Smoke ran the generated-project scenarios; its optional GitHub Actions lint was skipped because actionlint was unavailable. These results validate plan creation and the existing repository, not the future implementation tasks.
- Parent checks passed for numbered-plan admission, actual TSV index/status/dependency mapping, exact condition/acceptance digests, declared command grammar, context existence and diff whitespace. After the final witness-only clarification, the parent reran the affected policy/manifest checks.
- Two read-only document-review rounds found authority bypass, completion-scope, accounting, baseline-self-reference and witness-boundary issues. The parent incorporated the bounded corrections and verified the final mechanical witness split; no product execution ledger was opened and no runtime implementation review is claimed.
- Implementation task checkboxes remain open, and implementation completion witnesses have not yet been established.
- Recheck the current committed baseline and exact scope before implementation; read applicable directory AGENTS.md and required specifications directly. Preserve any intervening owner changes.
- The parent owns scope admission, validation acceptance, independent-review acceptance, lifecycle, commits and reporting. Read-only helpers may supply bounded evidence; no writable helper is authorized by this planning turn.
- No measured speedup or resource saving is claimed. Root plan files describe this repository's implementation work and are not copied as product-specific plans into the reusable template.
