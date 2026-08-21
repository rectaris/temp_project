# Complete verify-copier-update Skill integration

status: in_progress
primary_invariant: deliver the reusable isolated Copier update verification Skill with the exact generated validation permission and every inherited safety and compatibility requirement proven together
task_types:
  - planning_docs
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - CHANGELOG.md
  - .codex/skills/verify-copier-update/
  - scripts/check-copier-template.py
  - scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/validate-copier-update.py
  - template/.agents/skills/verify-copier-update/
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - copier.yml
  - docs/agent/spec-index.yaml
  - docs/plan/checked/2026/08/16-31/118-harden-original-repository-snapshot.md
  - references/template-development.md
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/run-copier-update.sh
  - template/.project-agent-workflow/scripts/update-from-copier.sh
  - tests/copier-update.sh
  - tests/test-verify-copier-update.py
  - tests/validation_tools/plan.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
  - git diff --check
validation:
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Install a concise verify-copier-update skill in the root repository and generated managed Skill layout, including aligned UI metadata, one directly linked workflow reference, one byte-identical executable helper, and one reserved discovery bridge.
  - Require explicit downstream repository, template repository, immutable source selector, external output directory, target-specific validation argv, and template-task trust inputs; reject dirty, non-root, symbolic-link, missing-ref, source-layout, pre-v1, and force-style bypass conditions before executing the update.
  - Resolve and record exact target and source commit OIDs, clone both repositories without hard links into a disposable same-filesystem workspace, preserve a safe relative Copier source relationship, sanitize the child environment, and never change the original downstream or template worktree, Git refs, index, or ignored files.
  - Use the downstream repository's supported generated update wrapper when present, use direct trusted Copier update only for a supported v1-or-newer namespaced baseline without that wrapper, and delegate ownership, conflict, rejection-file, unmerged-index, deletion, and managed-transition checks to the updated generated validator.
  - Run git diff checking, generated change-aware validation, every explicit target-specific validation command without a shell, then commit only inside the disposable clone and prove that the same source selector produces no second-update diff.
  - Emit a bounded local verification manifest and separate command logs with verified only after every required check passes, rejected only after an observed update or invariant failure, and blocked when a prerequisite prevents completion; do not store credentials, environment values, or raw repository paths in the manifest.
  - Add deterministic verified, rejected, blocked, dirty-source, dirty-target, unsafe-output, invalid-validation-command, and original-repository-preservation coverage without embedding curiretas-account paths, versions, product commands, or credentials in the generic Skill.
  - Keep root and generated Skill semantics, helper bytes, executable modes, Copier inventory, ownership reservation, smoke generation, and supported update behavior aligned, and finish with zero unresolved High or Medium independent-review findings.
replan_source: docs/plan/active/119-integrate-verify-copier-update-skill.md
replan_contract: docs/plan/replanned/contracts/119-integrate-verify-copier-update-skill.json
integration_gates:
  - plan 120 must complete and commit the exact generated helper-path validation rule first
  - the final independent review must report zero unresolved High or Medium findings across Plans 118, 120, and 121
successor_plans:
  - docs/plan/active/120-allow-generated-copier-verification-helper-compilation.md
  - docs/plan/active/121-complete-verify-copier-update-skill-integration.md
inherited_acceptance_digests:
  - sha256:d2b0ed89c0dbef0bfeb103385cd41a951e09a589690de2b9726394e9998187e6
  - sha256:0cb43db13b4153482d507a327385b83829d6cd4e3e90955c6d17f788d29571b4
  - sha256:88220b0a100257d13495e09659be96f2e386ed7353bc1495cb60eb7b6f14b8e9
  - sha256:e3a575d34fed5bc293e8e7442a2a68fe2814cffa8666e9a216064c071f98c158
  - sha256:d0117710f8c86df7e65c1132d0d8c84a16e676f9d9f40fd972ca82f5ab3e2b39
  - sha256:b8917301f15ee38f1b9f2d948627ffda18f95f08e5138a3b23fa3a0a06b05e10
  - sha256:308019cc71e5ea98d124915fbcfe9a918bf7dbf9fd353f5b56bb0e02f7bdf69e
  - sha256:1c327fc62693aea603557acfcc40ff9f3dfbd5826d111e95b51f04a6e113cad8
checked_summary_ja: 生成側の厳密な検証許可を含め、隔離したCopier更新検証スキルの全受入条件を確認する。

## Decisions

- Admit only the committed Plan 120 exact-path permission; do not broaden generated Skill script validation during integration.
- Preserve the concise Skill, bounded child environment, explicit trust boundary, original-repository snapshot guarantees, direct supported-v1 path, and generated-wrapper path.
- Require the real wrapperless Copier lane to reach `verified`, then run the complete authoritative suite exactly once after focused validation and independent review.
- Preserve Plan 119 diagnostics in concise validation notes and keep raw command output outside `docs/plan`.
- Use bounded parent integration for the inherited dirty candidate and retain final acceptance ownership in the main session.

## Tasks

- [ ] Admit the committed Plan 120 validation policy and review the remaining integration diff.
- [ ] Finish root/template Skill, inventory, ownership, smoke, validator, and changelog integration without changing the accepted safety boundary.
- [ ] Complete independent review and focused validation with zero unresolved High or Medium findings.
- [ ] Run the authoritative suite exactly once, archive Plan 121, and commit the integration-owned paths.

## Validation Notes

- This integration successor copies every Plan 119 acceptance item exactly.
- The prior authoritative suite is not completion evidence because it stopped in the real Copier lane before the exact generated helper path was permitted.
