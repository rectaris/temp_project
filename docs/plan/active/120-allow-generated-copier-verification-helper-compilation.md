# Allow generated Copier verification helper compilation

status: in_progress
primary_invariant: generated change-aware validation accepts the exact managed Copier verification helper path without accepting unrelated Skill scripts or unsafe paths
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/copier-update.sh
  - tests/validation_tools/plan.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/plan/checked/2026/08/16-31/118-harden-original-repository-snapshot.md
  - template/.project-agent-workflow/scripts/validate-changes.py
  - tests/validation_tools/support.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
  - git diff --check
validation:
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Install a concise verify-copier-update skill in the root repository and generated managed Skill layout, including aligned UI metadata, one directly linked workflow reference, one byte-identical executable helper, and one reserved discovery bridge.
  - Run git diff checking, generated change-aware validation, every explicit target-specific validation command without a shell, then commit only inside the disposable clone and prove that the same source selector produces no second-update diff.
  - Add deterministic verified, rejected, blocked, dirty-source, dirty-target, unsafe-output, invalid-validation-command, and original-repository-preservation coverage without embedding curiretas-account paths, versions, product commands, or credentials in the generic Skill.
  - Keep root and generated Skill semantics, helper bytes, executable modes, Copier inventory, ownership reservation, smoke generation, and supported update behavior aligned, and finish with zero unresolved High or Medium independent-review findings.
replan_source: docs/plan/active/119-integrate-verify-copier-update-skill.md
replan_contract: docs/plan/replanned/contracts/119-integrate-verify-copier-update-skill.json
integration_gates:
  - plan 121 must admit the committed exact-path validation rule and retain every source acceptance item
  - independent review must report zero unresolved High or Medium findings before authoritative validation
successor_plans:
  - docs/plan/active/120-allow-generated-copier-verification-helper-compilation.md
  - docs/plan/active/121-complete-verify-copier-update-skill-integration.md
inherited_acceptance_digests:
  - sha256:d2b0ed89c0dbef0bfeb103385cd41a951e09a589690de2b9726394e9998187e6
  - sha256:d0117710f8c86df7e65c1132d0d8c84a16e676f9d9f40fd972ca82f5ab3e2b39
  - sha256:308019cc71e5ea98d124915fbcfe9a918bf7dbf9fd353f5b56bb0e02f7bdf69e
  - sha256:1c327fc62693aea603557acfcc40ff9f3dfbd5826d111e95b51f04a6e113cad8
checked_summary_ja: 生成プロジェクトの変更検証で、管理対象のCopier検証helperだけを安全にコンパイル検査できるようにする。

## Decisions

- Permit only `.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py` in the generated `is_python_compile` path predicate; do not permit a wildcard Skill scripts directory.
- Change only the generated validation-command policy. Preserve the broader but separate root repository policy unless a failing root case proves another change is required.
- Add a positive parser regression for the exact helper path and negative regressions for another Skill path, path traversal, an absolute path, and a non-Python path.
- Preserve the relative `_src_path`, temporary locked uv environment, and failure-log diagnostics in the real wrapperless Copier fixture.
- Use bounded parent implementation because this plan changes validation authority over an inherited dirty test slice; require independent read-only review before validation.

## Tasks

- [ ] Add failing positive and negative generated-command parser regressions.
- [ ] Implement the exact helper-path exception without weakening existing absolute-path, traversal, suffix, script, or hook checks.
- [ ] Prove generated command selection and the real wrapperless Copier update lane with zero unresolved High or Medium review findings.
- [ ] Run focused and authoritative validation once for this slice, record evidence, and commit only Plan 120-owned paths.

## Validation Notes

- Plan 119 authoritative validation reached the real Copier lane and exposed `ValidationCommandError` for the generated helper path after the update and generated validator had succeeded.
- The earlier absolute `_src_path` result was a fixture defect and is not the validation-authority design change addressed by this plan.
