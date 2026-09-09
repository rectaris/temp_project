# Admit lineage rebinding for checked predecessors

status: checked
primary_invariant: a lineage rebinding may restate a former active reference as the same plan id's checked archive only when that archive is unambiguous and checked, and it still changes no plan identity, no status, and no unadmitted reference
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/plan/checked/2026/08/16-31/241-admit-lineage-rebinding-for-divergent-successors.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - A lineage rebinding admits a replacement that restates a former active reference as the same plan id's unambiguous checked archive, and rejects a target that is missing, ambiguous, not checked, a different plan id, still resident at the active path, or otherwise unadmitted.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:5caac2048dd18c5ce85281cb78d84793f472e04816838e4a670b56fbb440c0cb","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/241-admit-lineage-rebinding-for-divergent-successors.md
successor_plans:
  - none
integration_gates:
  - do not change the activation record gate; a deferred baseline with a stopped reason stays the only route that also enters in_progress
  - do not change how a replanned source resolves to a checked successor; that replacement class stays byte-for-byte as Plan 241 checked it
  - do not activate any backlog plan in this change; reactivating a rebound successor is separate work
checked_summary_ja: 差し戻し済み後続プランが、チェック済みアーカイブになった先行プランへの参照を解消できない欠陥を修正した。`rebind_lineage` に第二の置換クラスを追加し、`activation_checked_pairs()` が同一プラン ID の一意なチェック済みアーカイブに解決できる場合に限って、旧 active 参照の書き換えを許可する。置換対象が不在、曖昧、未チェック、別プラン ID、active 位置に実体が残存、または前後にパストークン文字が続く場合は拒否する。共有パターンと activation 経路は無変更のまま維持した。

## Decisions

- Name the blocked referent before naming the fix. The object that cannot progress is not one plan. It is a backlog-resident or deferred replan successor whose `predecessor_plans`, `context_files`, `integration_gates`, or body still names a `docs/plan/active/` path that has since become a checked archive. `docs/plan/backlog/187-verify-plan183-successor-acceptance.md` is the first observed instance and ten backlog plans sit behind it.
- Fix a contradiction between two documented rules, not a missing feature. Successor Backlog Deferral instructs removing `completion_deferred_reason` and `replan_reason_codes`. The only operation that could rewrite an active reference to its checked archive is a `kind: activation` record, and that record requires a `deferred` baseline carrying a non-empty `completion_deferred_reason`. `backlog` cannot re-enter `deferred`, so a successor sent down the sanctioned deferral path can never resolve its lineage.
- Widen `rebind_lineage` rather than `activation`. `rebind_lineage` is already the designated operation for an unresolvable reference in an unstarted plan, already permits `predecessor_plans`, `context_files`, and `integration_gates`, already requires `status` in `deferred` or `backlog`, and already forbids a status change. Only the admitted replacement class is missing. Widening `activation` instead would let a backlog plan resolve its lineage and enter `in_progress` in one transaction, which removes the proof that a plan leaving `deferred` was genuinely stopped.
- Prove the target with the primitive the activation route already trusts. Resolve a checked replacement through `activation_checked_pairs()`, which requires the same plan id, the same file name, an existing archive whose `status` is `checked`, and an unambiguous single match. Reusing it keeps the two routes from drifting apart, and it already rejects a former active path that still holds a file.
- Keep reactivation a separate act. Rebind while the plan is still `backlog`, then reactivate through the route the specification already describes: move the file under `docs/plan/active/`, restore an active status, and re-add the active index row. `validate_lifecycle_evolution` already accepts a `backlog` baseline reaching `in_progress` with no protected-field change, so no further mechanism is needed.
- Correct the section label to match its referent. The specification section is titled `Replanned Predecessor Lineage Rebinding`, and its opening sentence defines the operation as being for a replanned source. After this change the operation admits two replacement classes, so the title names less than the operation does. Retitle it and state the two classes separately, so a later agent looking for a checked predecessor finds the rule.
- Admit the checked class for any unstarted referrer. Independent review found that the code gates only on `status` in `deferred` or `backlog`, so restricting the written rule to a backlog referrer would describe less authority than the code grants. A backlog referrer remains the reason the class exists, and a `deferred` referrer still cannot enter `in_progress` directly without its activation record, so the wider admission changes no lifecycle authority.
- Bound the reference token at the new admission site, not in the shared detector. `ACTIVE_REFERENCE_RE` has no right-hand boundary, so a longer path token ending in an active plan path, such as one carrying a `.bak` suffix, matches. A first attempt anchored the shared pattern, and independent review measured that this weakened two unrelated callers: the `unresolved` completeness scan in `validate_activation_reference_transition` and `resolve_active_references`. Both use the pattern to prove that no live active reference remains, so a narrower pattern makes a real reference invisible and admits an activation the current gate rejects. The boundary now lives only in the checked-archive branch, which refuses to restate text where the reference is extended into a longer path token on either side. Trailing sentence punctuation is not treated as an extension, so a reference written at the end of a sentence still moves. The shared pattern, the activation route, and the replanned class are byte-unchanged.

## Tasks

- [x] Admit a second replacement class in `validate_lineage_reference_transition`: an old reference that names one active plan path which `activation_checked_pairs()` resolves to the same plan id's checked archive, where the new text equals the old text under exactly that substitution.
- [x] Keep every existing gate unchanged: the replanned replacement class, the protected plan identity comparison, the `deferred` or `backlog` status requirement, and the prohibition on changing status.
- [x] Reject an unadmitted target: an active reference with no checked archive, an ambiguous archive, an archive that is not `checked`, a different plan id, an active path that still holds a file, and a replacement that changes any text outside the resolved substitution.
- [x] Retitle the specification section to name both admitted replacement classes and state the checked-archive class, in `docs/agent/SPEC_PLAN_WORKFLOW.md` and its template counterpart.
- [x] Add regression tests to `tests/test-plan-restructure.py` covering an admitted checked-archive rebinding, each rejection above, and an unchanged replanned-source rebinding.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Independent review ran three rounds. Round 0 returned zero High and zero Medium findings and four Low findings. Round 1 returned one Medium, which was accepted and reverted rather than argued. Round 2 returned zero High and zero Medium findings and a verdict of acceptable. Round 0 measured a 4028-case differential between the previous and current `validate_lineage_reference_transition` and found the replanned and identifier classes accept and reject identically; the only divergences are the intended checked-archive admissions.
- The new admission is strictly stronger than the activation route whose primitive it reuses. `activation_checked_pairs()` matches on plan id and file base name, rejects an ambiguous archive, and requires the archive to exist with `status: checked`. The rebinding route additionally rejects a former active path that still holds a file, which the activation route does not check.
- Review confirmed the whole rebind pipeline accepts the real blocked case end-to-end, read-only and without mutating any plan artifact: a `rebind_lineage` specification moving Plan 187's `predecessor_plans` entry from `docs/plan/active/186-bind-connected-copier-fixture-checker.md` to its checked archive passes `validate_rebinding_specs`, `validate_lifecycle_evolution` on both sides, `validate_current_plan_rules`, and the immutable chain checks.
- A later agent rebinding Plan 187 must send exactly one replacement, for `predecessor_plans`. The reference occurs three times in that plan's chain projection but only twice in its live bytes, because the live `context_files` entry was already repaired, and `validate_rebinding_specs` applies the same replacements to both sides. A `context_files` replacement therefore rejects with an occurrence mismatch. The stale projection entry is neutralised by `project_context_archive_relocation` inside `validate_lifecycle_evolution`, not by a rebinding. The `successor_plans` occurrence is immutable lineage and is out of scope by design.
- Round 2 also raised a left-side boundary asymmetry: the occurrence scan bounded only the right side, so a reference preceded by a path-token character was still restated. The corpus held no such occurrence, but the guard is now symmetric and a regression case covers it.
- Authoritative suite run once after the review closed: `tests/test-plan-restructure.py` 158 tests OK, `scripts/restructure-plan.py --verify` passed, `scripts/check-copier-template.py` passed, `scripts/lint-project-workflow.sh` passed, `tests/smoke.sh` passed, `git diff --check` clean.
- Remediation round 1 answered all four Low findings, and one of its answers was wrong. Anchoring `ACTIVE_REFERENCE_RE` was measured by round 2 review to weaken the activation completeness scan, which uses the same pattern to prove absence rather than to admit a replacement. Round 2 reverted the shared pattern to its committed form and moved the boundary into the checked-archive branch alone, so the activation route and the replanned class stayed byte-unchanged while a `.bak` sibling now rejects for a named reason instead of being silently restated.
- A parent-run negative control removing the admitting branch made the new test fail with `names no checked archive and no replanned source with a checked successor`, and review mutation-tested each rejection sub-assertion against a distinct branch mutant.
- No backlog plan was activated or rebound by this change. Reactivating Plan 187 remains separate work.
