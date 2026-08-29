# Reject unmodelled Copier writes to the sanctioned destination

status: checked
primary_invariant: no fixture operation writes the sanctioned destination through a Copier command other than the modelled update without the checker rejecting it
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
implementation_tier: 2
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
  - docs/plan/checked/2026/08/16-31/231-scope-fixture-alternate-path-rule.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/237-restore-the-resolution-model-as-the-single-update-authority.md
successor_plans:
  - none
integration_gates:
  - do not edit tests/copier-update.sh; Plan 227 owns the fixture runtime
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
  - do not reject a Copier copy whose destination does not settle; the lane copy in the committed fixture writes an unsettleable path and must stay accepted
checked_summary_ja: Copier の copy と recopy が更新対象プロジェクトへ書き込む経路を検査対象に加え、更新子の前に実行されると証明できる最初の 1 回だけを既定の作成として許可し、それ以外を拒否した。

## Decisions

- Keep this invariant separate from the update authority. Plan 237 fixed which operations run a Copier update. A Copier copy or recopy is not an update, so covering it is a second independently validatable invariant and was ruled out of Plan 237 by independent review.
- Read a destination only when it settles. A copy whose destination this checker settles nothing for must stay accepted, because the committed fixture copies into a loop-bound lane path that settles to no path at all. Rejecting an unread copy destination would block the fixture runtime work. Independent review measured that this settles-nothing case, not the expansion case, is the one the integration gate depends on.
- Reject only a proven reach. The rule fires when a settled Copier write destination is not proven lexically separate from the sanctioned destination, which is the narrowest reading that closes the disclosed hole.
- Treat the existing acceptance as accidental, not as an invariant. The previous validator rejected this shape only when the surrounding text happened to contain the update word, so no checked behaviour is being weakened here.
- Model the one creation the fixture must perform. Implementation found that `tests/copier-update.sh:1778` copies into the exact destination the modelled update child updates, because that copy is how the sanctioned project is created. A rule that rejects every proven reach therefore contradicts this plan's own integration gate. The repository owner approved narrowing the rule to unmodelled writes: the earliest write proven to run before the update child is the modelled creation, and every additional write and every write at or after the child is rejected.
- Answer separation with the existing predicate. A read copy destination is compared against the sanctioned destination with `_lexically_separate`, the same predicate the alternate-path prohibition uses, and the copy rule rejects exactly what that predicate does not prove separate. A path written inside the other, a path no written text anchors, a differing segment carrying an expansion, and an update-child destination the checker cannot read are therefore all reaches, so this rule is never weaker than the prohibition it is modelled on.
- Bind the exemption to a proven running place. A write inside a function body runs where the body is called, and a write inside a loop or branch that reaches past the child runs again later, so neither takes the creation exemption. Independent review confirmed a body written before the child but called after it is rejected.

## Tasks

- [x] Read the Copier subcommand of a modelled operation and collect the settled write destination of a copy or recopy in the same way the update reading collects an update destination.
- [x] Reject a reachable operation whose settled Copier write destination is not proven lexically separate from the sanctioned destination, except the earliest such write proven to run before the modelled update child, and accept one whose destination does not settle.
- [x] Add regression tests covering a copy and a recopy into the sanctioned destination through a helper the fixture does not define, a copy into a separate project, and a copy whose destination carries an unsettled expansion.
- [x] Confirm the committed tests/copier-update.sh still passes --check without editing it, including the lane copy that writes an unsettleable path.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Implementation deviated from the literal task-2 wording with repository-owner approval. Settling every Copier write destination in `tests/copier-update.sh` showed that line 1778 writes the exact destination the modelled update child at line 1859 updates, because that copy creates the sanctioned project. Rejecting every proven reach would have failed this plan's own integration gate, and a bounded descope was unavailable because the plan carries one acceptance item. The owner chose to narrow the rule to unmodelled writes rather than stop the plan.
- Independent review ran three rounds against the working tree and closed with zero High, Medium, or Low findings. Round 0 raised two Mediums: the rule switched itself off when the update child's own destination was unreadable, and an unanchored copy destination was never a reach. Round 1 moved the polarity into `_writes_a_reserved_path` and fixed the anchor case. Round 2 raised one further Medium, that a differing segment carrying an expansion was still accepted where the alternate-path prohibition rejects it; the answer removed the separate reach predicate and reused `_paths_are_lexically_separate`, so both rules now read separation through one implementation.
- Parent-side probing before the review found a bypass the first implementation admitted: a copy written inside a function body before the update child but called after it took the creation exemption, because a written place is not a running place. `_precedes_the_child` now denies the exemption inside any function body and inside any loop or branch reaching past the child, and four regression tests bind it.
- Evidence recorded by the review: an exhaustive differential over 268,324 settled-path pairs found no input where the final predicate accepts what the previous one rejected, and every stricter case carries an expansion segment. Removing the `not candidate` guard produces 39 findings on an otherwise compliant fixture, so the guard separating "not read" from "not proven separate" is load-bearing. On the committed fixture exactly one of 18 settled copy destinations is not proven separate, and it takes the single creation exemption.
- A parent-run negative control that replaced `_check_copier_writes` with a no-op failed 12 of the new tests while the acceptance cases still passed, so the suite binds the enforcement rather than the surrounding reading.
- Two residuals are disclosed and stay open, both inherent to the approved narrowing and both bounded to pre-child state the modelled child then updates. The exempted creation's template operand and `--vcs-ref` are unread, so a creation from an unmodelled source is accepted. A loop lying entirely before the child may run that creation more than once. Neither reaches a mid-transition replacement of the sanctioned destination.
- Authoritative suite run once after the review closed: `tests/test-copier-fixture-validator.py` 350 tests OK, `copier_fixture_validator.py --check tests/copier-update.sh` passed, `git diff --check` clean, `scripts/lint-project-workflow.sh` passed, `tests/smoke.sh` passed. `tests/copier-update.sh` was neither edited nor executed.
