# Check tracked text hygiene in local validation instead of only at the release boundary

status: in_progress
primary_invariant: Every rule the release boundary enforces on tracked text is reachable from a local validation run, so no tracked-text defect can first become visible after a push.
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
  - {"evidence":"A read-only prototype scanned all 843 tracked files and found five violations: a blank line at end of file in agents/openai.yaml, two 2026-07 checked archives, and migrations/v0.2.0.md, plus a missing final newline in tests/root-plan-lifecycle.sh. No trailing whitespace and no carriage return exist, so the rule needs no exclusion list.","kind":"bounded_prototype"}
  - {"evidence":"copier_inventory.py already carries the root-only command scripts/check-yaml.py in SOURCE_REQUIRED, so a root-only checker has an established registration path that implies no generated copy.","kind":"existing_mechanism"}
  - {"evidence":"git diff --check exists only in .github/workflows/ci.yml:74, and tests/smoke.sh:325 asserts only that the generated workflow contains those commands. No local command reads this repository's tracked text, so a blank line at end of file first appeared as a failed release run.","kind":"reproduced_defect"}
completion_conditions:
  - Required local validation runs a repository-wide tracked-text check that refuses trailing whitespace, a blank line at end of file, a missing final newline, and a carriage return.
  - Every tracked text file in this repository satisfies that rule, so the check starts from a clean state rather than a grandfathered exclusion list.
completion_witness_map:
  - {"condition_sha256":"sha256:bcde34a7345c1e1fe449f31165dce2cae545825b5540daa18eeeb22c455b5a65","witness":"python3 tests/test-text-hygiene.py"}
  - {"condition_sha256":"sha256:fe4e71d711443acf83cfecc282a46ac14c37830b57b52ea78cededb9c3bb1dd9","witness":"python3 scripts/check-text-hygiene.py"}
write_scope:
  - scripts/check-text-hygiene.py
  - scripts/lint-project-workflow.sh
  - scripts/project_workflow/copier_inventory.py
  - tests/test-text-hygiene.py
  - agents/openai.yaml
  - docs/plan/checked/2026/07/01-15/001-initial-package.md
  - docs/plan/checked/2026/07/01-15/002-copier-template.md
  - migrations/v0.2.0.md
  - tests/root-plan-lifecycle.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/01-15/329-release-v147-for-downstream-improvement-flow.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-text-hygiene.py
  - python3 scripts/check-text-hygiene.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A contributor learns about a tracked-text defect from a local validation run rather than from a rejected release, because the rule the release boundary enforces now also runs before the push.
  - The five files that already violated the rule carry the same content with the defect removed, so the new check needs no exclusion and no reader has to learn which paths are exempt.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:52929e0bd3d6ccebc640c63f95967a67067cdeb55972e3e814545ba6877e26be","stage":"focused","witness":"python3 tests/test-text-hygiene.py"}
  - {"acceptance_sha256":"sha256:9061c39dfd2ff6e12b8ceb231af8a88e2e8eea5f61e41daee2b0c7c63bdb6bb1","stage":"focused","witness":"python3 scripts/check-text-hygiene.py"}
checked_summary_ja: 追跡テキストの体裁を、公開時ではなく手元の検証で検出する。

## Decisions

- Scan the tracked file set rather than a commit range, because a range-based rule reaches a different conclusion depending on which range is taken, and the release failure came from exactly that difference.
- Refuse a missing final newline as well, even though the release check does not, because it is the same class of defect and the repository holds exactly one instance of it.
- Repair the five existing violations instead of exempting them, so the rule covers every tracked file and no reader has to consult an exclusion list to know what is checked.
- Keep the checker root-only. A generated project already receives the range-based check in its own workflow, and widening the rule to generated projects is a separate decision with its own downstream effect.

## Tasks

- [ ] Add scripts/check-text-hygiene.py, which reads the tracked file set, skips files holding a NUL byte, and reports every violation with its path and line.
- [ ] Register the checker and its suite in required lint and add the command to the deterministic source inventory.
- [ ] Add tests/test-text-hygiene.py, which proves each rule refuses a constructed defect and that removing a rule fails the suite.
- [ ] Remove the blank line at end of file from the four named files and add the missing final newline to tests/root-plan-lifecycle.sh.

## Validation Notes
