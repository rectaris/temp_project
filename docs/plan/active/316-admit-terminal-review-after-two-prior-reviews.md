# Admit one terminal review after two or three verified prior reviews

status: in_progress
primary_invariant: An owner-authorized terminal continuation consumes at most one existing review allowance after two or three verified prior reviews, without reopening stopped histories, replenishing budgets, or bypassing acceptance gates.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At 2db7d851147df64a5f1fb0c5e8784458b3cec9d9, existing isolated fixtures with one review in each prior epoch make continue-final return exit 1 for exactly three prior reviews, without changing predecessors or registries.","kind":"reproduced_defect"}
  - {"evidence":"The existing terminal CLI already verifies the exact epoch-zero ancestor, continuation consumption, owner authorization, reviewer registry, unchanged plan bytes and descendant source adoption. Its three-review positive and exhausted-total negative tests pass.","kind":"existing_mechanism"}
  - {"evidence":"validate_execution_epoch, continue_state, validate_state and record_event expose the terminal eligibility and both stored-history and pre-admission review accounting checks. Existing final_continuation_fixture can exercise both layouts and prior-review distributions.","kind":"existing_mechanism"}
completion_conditions:
  - Terminal continuation admits exactly one review in epoch one after one or two actual reviews in its verified epoch-zero ancestor, binds every actual prior reviewer admission, and preserves both stopped ledgers.
  - A terminal epoch admits at most one new formal review even when the cumulative four-review maximum has unused room; stored-history verification and CLI admission both reject a second terminal review before accepting effects.
  - Historical schema-one bounds, the existing three-review route, owner authorization, exact plan/source and registry bindings, replay and fork refusal, no worker attempt and no later continuation remain enforced.
  - Root and generated tooling and guidance agree on two or three verified prior reviews, one terminal correction and review, forfeiture of unused room, immutable stopped records and the unchanged cumulative maximum.
completion_witness_map:
  - {"condition_sha256":"sha256:cbf1cbe619c00767e74f05782f5c564b9e016eae25ad43dd01d559dab1276784","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:508a27035eb19611c2fac6879182ab0217276d83bb9c2b60185227adc10ec565","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:68a4e1952bb206de10e0b16aea33dafef97cb303b39eb04d8c72994bc73b53e6","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:515f8f52237365ccc4170396ce3560a0e3c4b14735c635a751bff94c8143bcb7","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - AGENTS.md
  - template/AGENTS.md.jinja
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
required_specs:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An owner can authorize one terminal correction and independent review after two or three verified prior reviews, while stopped records, existing identity and validation gates, the four-review maximum and the prohibition on further continuation are preserved.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:23348bde11fb3a06026be1168ecdb743d543975e2b8d751cfe2493a669477af6","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
checked_summary_ja: 過去2回のレビューで停止した作業にも、最後の修正とレビューを1回だけ認める。

## Decisions

- The owner explicitly approved the separate bounded policy implementation on 2026-09-16 by accepting the question titled 再開条件の限定的な変更を承認する. Preserve stopped records, the cumulative maximum of four, and every existing acceptance gate.
- Use parent-direct implementation because this change governs lifecycle and review authority. Initialize a separate execution ledger and observe its review route before product edits; keep formal independent review, exact-target adversarial preflight and authoritative validation.
- Extend continue-final only for an ungrouped parent-direct epoch-one stop caused solely by parent_remediation_budget_exhausted, with one local formal review and one or two verified original reviews. The actual original count must equal the count bound into the stopped continuation.
- Keep the existing schema-two field shape and all source, plan, owner, ancestor and registry bindings. Keep historical schema-one limits unchanged. The terminal child permits one correction and at most one new review; any otherwise unused allowance is forfeited.
- Enforce the terminal one-review bound both before reviewer-registry admission and while reading stored event history. Do not rely only on the cumulative limit, which leaves room for two reviews when the prior count is two.
- Preserve the existing three-review and exhausted-total regressions. Add root and generated two-review cases, a stored-history second-review rejection, and refusal when the continuation already used two local reviews.
- Do not change plan 364 acceptance, product files, stopped ledgers or existing registries as an effect of this policy implementation. Adoption and any later product edit still require a separately admitted owner-bound terminal continuation.

## Tasks

- [ ] Implement the bounded prior-count admission and cross-check it against the verified original ledger.
- [ ] Enforce one terminal review independently of the cumulative budget at both record and history-read boundaries.
- [ ] Extend the existing isolated fixtures and regressions for two-review root/generated admission, retained historical behavior and refusal before effects.
- [ ] Align both implementation copies and the root/generated workflow, orchestration and entrypoint guidance.
- [ ] Review the exact in-scope diff independently, run focused and authoritative validation, commit the policy separately and publish it before any adoption by plan 364.

## Validation Notes

- The separately preserved plan364 candidate has digest sha256:a3061ecb55710d7e5d4e028b0fd11656de47ab4568d5dc111c70a25a9ac0efe3. Its epoch-zero ledger remains byte-identical with digest sha256:fbde1cd3459e07b061ca4a42575456fb85c032fbb674e0b21658364363b519e6. These are preservation observations, not write authority.
