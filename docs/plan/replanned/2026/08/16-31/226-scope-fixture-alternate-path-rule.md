# Scope the fixture alternate-path rule to the sanctioned destination

status: replanned
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
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
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
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
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/226-scope-fixture-alternate-path-rule.md
replan_contract: docs/plan/replanned/contracts/226-scope-fixture-alternate-path-rule.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/230-resolve-fixture-destinations-fail-closed.md
  - docs/plan/active/231-scope-fixture-alternate-path-rule.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
checked_summary_ja: fixture checkerのalternate_path規則を送り先単位へ限定し、既存の正規laneとbypass拒否を保つ。

## Decisions

- Plan 185 stopped because its declared write_scope could not satisfy its bound focused witness. Activating the fixture transition turns `_is_transition` true, and the global `alternate_path` rule then rejects 37 pre-existing accepted Copier lanes that Plan 185 was not allowed to touch.
- Reconstruct the validation method rather than the requirement. The rule's own docstring already describes a same-project prohibition, so making the implementation destination aware restores the intended boundary instead of weakening it.
- Keep the bypass rejections intact. A renamed helper or a local alias that still reaches the sanctioned destination must stay rejected, because Plan 186 is chartered on that prohibition.
- Own the checker and its test together, because the rule change is only acceptable with the mutation coverage that proves the prohibition still holds.

## Tasks

- [ ] Reproduce the 37 alternate_path findings by supplying the committed fixture plus an accepted transition sample to the checker.
- [ ] Make the alternate-path rule resolve each reachable update operation's destination project and reject only operations that can reach the sanctioned child's destination.
- [ ] Keep every existing rejection test passing and add mutation coverage for a renamed helper, a local alias, and a differently written same-destination dispatch.
- [ ] Confirm the committed tests/copier-update.sh still passes --check without editing it.
- [ ] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Pending. The 37 rejected lanes and the two cleanup findings are recorded in the Plan 185 archive.
- Reproduced the 37 alternate_path findings by checking the committed tests/copier-update.sh together with an accepted transition sample. A destination-aware rule reduced them to one residual alternate_path at fixture line 691, beside the release_path and guardian findings at line 21 that Plan 227 owns.
- Built the destination-aware rule as a candidate and preserved it on the local branch `plan-226-candidate`. It reached 160 passing tests, a clean `--check tests/copier-update.sh`, and a clean `git diff --check`, and it was never committed to `dev`.
- Ran seven independent review rounds against that candidate. Each round cleared its predecessor findings and each round found new ones: 1 finding, then 4, 3, 2, 2, 1, and 3. The parent remediation budget of two rounds was exhausted at round three.
- Every round-seven finding is a regression against the rule this plan replaces, because that rule rejects every reachable update dispatch unconditionally. Reproduced all three: a function body that settles a destination against its definition value rather than its call environment, a launcher option that hides the effective command, and a symbolic link moved to a second path.
- Diagnosed the cause as two coupled invariants. Rejecting only a provably shared destination is sound only over a resolution model that reports unproven whenever the written shell text does not determine a destination or an alias. This plan owns the rule, so every resolution gap surfaced as a rule defect and could not be validated apart.
- Authoritative validation was never run, because the review gate never cleared.
- Stopping under `multiple_independent_invariants` and `parent_remediation_budget_exhausted`. The requirement is unchanged and moves to the successors.
