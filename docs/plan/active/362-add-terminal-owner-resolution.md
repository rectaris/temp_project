# Add bounded owner resolution after the fourth review

status: in_progress
primary_invariant: Four formal reviews remain the immutable automated-review maximum; only one exact owner-bound Medium-only terminal resolution may complete without a fifth review, while High findings, replay, forks, and further correction remain blocked.
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
  - {"evidence":"Schema-3 epoch evidence already binds the three predecessor ledgers, four admitted reviewer sessions, the cumulative review limit, the continuation registry, the reviewer registry, and the exact stopped child identity.","kind":"existing_mechanism"}
  - {"evidence":"Plan 369 reached its fourth formal review with one bounded Medium finding and no High finding; the current policy stops all writes and offers no owner resolution that can preserve the four-review ceiling.","kind":"reproduced_defect"}
  - {"evidence":"Terminal continuation already supports an owner-authorized descendant source HEAD while preserving stopped ledgers and requiring exact plan bytes, registry identities, adversarial preflight, and parent-owned validation.","kind":"existing_mechanism"}
  - {"evidence":"Parent-direct review identity, lifecycle identity, append-only registry records, and focused and authoritative validation events provide the primitives needed to bind one final owner acceptance to exact diff and evidence digests.","kind":"existing_mechanism"}
completion_conditions:
  - An epoch-3 parent-direct run stopped after exactly four formal reviews may enter owner resolution only when the latest review has Medium findings and no High finding, every ancestor and registry binding verifies, and one mode-0600 owner authorization binds the finding evidence, exact allowed paths, source relationship, and child destination.
  - Owner resolution permits one parent correction, no worker attempt and no formal review, then requires current-target focused and authoritative validation plus a separate owner acceptance bound to the exact diff, validation events, finding evidence, plan, source, and execution identities before completion or archive.
  - The four-review maximum, stopped ancestor bytes, existing continuation routes, High-finding stop behavior, replay and fork refusals, and root/generated policy and implementation alignment remain unchanged outside the new terminal owner-resolution path.
  - Deterministic root-policy checks require the owner-resolution boundary, the unchanged four-review ceiling, and the prohibition on treating a new session, plan, registry, or successor as review-budget replenishment.
completion_witness_map:
  - {"condition_sha256":"sha256:56f31fee303beb35049f920e1acf1cc79dc13513b19a4023e984f155071149a7","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:ee08d476b0085a54c24ec25ad32a51f2922555448c4ccadaf7e8e2617ba6b80e","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:38db95f2bc2614d9363778d4fe62ff4932f949e5995f8fb437ec926ba2199d07","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:7c2cddaa3ba74cf6ba2593810fcc12c19fbaec8c20f15baee7cf16c01e27857b","witness":"python3 scripts/check-root-agent-policy.py"}
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
  - scripts/check-root-agent-policy.py
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/plan/backlog/369-repair-parent-direct-lifecycle-records-successor.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - After the fourth formal review, automation remains stopped; only an exact owner-authorized Medium-only terminal resolution can admit one final bounded parent correction, and High findings or mismatched historical evidence remain blocked.
  - The terminal correction cannot complete or archive until focused and authoritative validation for the resulting exact target pass and a separate owner acceptance binds that target and evidence; no fifth formal review or further correction is available.
  - Existing ledgers and four-review behavior remain compatible, and root policy, generated policy, root implementation, and generated implementation describe and enforce the same owner-resolution boundary.
  - Deterministic policy checks reject removal of the four-review ceiling, session-based budget reset, or completion without the bounded owner-resolution authorization and acceptance path.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:4b8c7bbfe33372bf5d4ebfb5507db820c4de3d80b42a4b6a001f7f7d2fc61348","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:780d66e47377d8ec32ecf6c2da32cf23943fae7d55f5f2cd134c108a123d596a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:99f24fa582980b89cac8177099ca4e33b705f9fe96751f4625895990e8316a48","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:f1c1dc29ca469a22ebb98ff838f9ac065a11c33d4fa83760aa14101f0a9b58b0","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
checked_summary_ja: 4回目のレビュー後に自動反復を再開せず、owner が限定修正と最終受け入れを担う終端解決経路を追加する。

## Decisions

- Keep four formal reviews as the immutable cumulative automated-review maximum; owner resolution adds no review slot and never reopens a stopped ledger.
- Define owner resolution as a new one-shot child execution bound to the complete epoch-0 through epoch-3 chain, the existing continuation and reviewer registries, the latest Medium-only review receipt, and external finding evidence.
- Require separate pre-correction authorization and post-validation owner acceptance. The final acceptance binds the exact resulting parent-direct review identity and the focused and authoritative validation events.
- Permit one parent-direct correction only. Refuse workers, a second correction, formal review, High findings, altered plan or invariant, widened write scope, registry replacement, replay, fork, and every later continuation.
- Support descendant-source adoption for a separately published policy implementation while preserving dirty product bytes and every historical ledger byte; conflicts stop instead of dropping either side.
- Apply the rule generically to eligible executions. Plan 369 is evidence and the first intended consumer, not a special-case identifier in reusable policy or code.

## Tasks

- [ ] Specify the owner-resolution state, authorization and acceptance schemas, exact eligibility predicates, retained review ceiling, and failure behavior in root and generated workflow policy.
- [ ] Implement a one-shot owner-resolution command and ledger events that verify all four review admissions, stopped ancestors, registries, source relationship, allowed paths, finding evidence, and owner authorization before granting one parent correction.
- [ ] Require post-correction focused and authoritative validation events and record a separate exact-target owner acceptance before completion or archive; reject review, worker, retry, replay, fork, and High-finding paths.
- [ ] Add regression fixtures for eligible Medium-only resolution, High refusal, missing or altered evidence, oversized or malformed authorization, source adoption, dirty-byte preservation, validation ordering, owner-acceptance mismatch, and all existing continuation routes.
- [ ] Mirror implementation and policy changes into the generated template and update deterministic root-policy checks.
- [ ] After the generic policy is published, use its documented adoption path to continue plan 369 without deleting or rewriting its existing ledgers or replenishing its four-review budget.

## Validation Notes

- Decision audit outcome: the four-review ceiling addresses non-terminating automated review loops and remains unchanged; the missing boundary is a terminal transfer of responsibility to the owner.
- Owner direction: 「提案の方針で進めるためのプランを作成せよ。」
- This plan is created in backlog because plan 369 remains the sole in-progress plan. Activation must not rewrite, reopen, or discard plan 369 or its external execution evidence.
- Activation parked plan 369 through Successor Backlog Deferral rather than rewriting it. `status: in_progress` became `status: backlog` and the file moved to `docs/plan/backlog/`; nothing else changed. A schema-4 successor cannot enter `deferred`, so this is the only admitted park, and reversing it restores the exact bytes whose digest the epoch-0 through epoch-3 ledgers bind. Reactivation must move the file back and restore that one word, with no other edit.
- Descendant-source adoption compares only the predecessor source commit, the adopted commit, and the working tree. An intermediate commit that moves plan 369 and moves it back therefore leaves it eligible, provided the adopted commit carries the restored path and bytes.
- This plan's `context_files` entry for plan 369 follows that move and must follow it back on reactivation.
