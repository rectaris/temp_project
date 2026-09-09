# Add isolated downstream Copier update verification

status: replanned
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
replan_reason_codes:
  - multiple_independent_invariants
  - parent_remediation_budget_exhausted
write_scope:
  - CHANGELOG.md
  - .codex/skills/verify-copier-update/
  - docs/plan/
  - scripts/check-copier-template.py
  - scripts/plan_validation_commands.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/validate-copier-update.py
  - template/.agents/skills/verify-copier-update/
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-verify-copier-update.py
  - tests/test-validation-tools.py
  - tests/validation_tools/plan.py
context_files:
  - AGENTS.md
  - copier.yml
  - docs/agent/spec-index.yaml
  - references/template-development.md
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - template/.project-agent-workflow/scripts/run-copier-update.sh
  - template/.project-agent-workflow/scripts/update-from-copier.sh
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
  - python3 scripts/check-copier-template.py
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
primary_invariant: preserve the complete source acceptance baseline
replan_source: docs/plan/active/117-verify-copier-update-skill.md
replan_contract: docs/plan/replanned/contracts/117-verify-copier-update-skill.json
integration_gates:
  - combined successors must satisfy every source acceptance item
successor_plans:
  - docs/plan/active/118-harden-original-repository-snapshot.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
inherited_acceptance_digests:
  - sha256:d2b0ed89c0dbef0bfeb103385cd41a951e09a589690de2b9726394e9998187e6
  - sha256:0cb43db13b4153482d507a327385b83829d6cd4e3e90955c6d17f788d29571b4
  - sha256:88220b0a100257d13495e09659be96f2e386ed7353bc1495cb60eb7b6f14b8e9
  - sha256:e3a575d34fed5bc293e8e7442a2a68fe2814cffa8666e9a216064c071f98c158
  - sha256:d0117710f8c86df7e65c1132d0d8c84a16e676f9d9f40fd972ca82f5ab3e2b39
  - sha256:b8917301f15ee38f1b9f2d948627ffda18f95f08e5138a3b23fa3a0a06b05e10
  - sha256:308019cc71e5ea98d124915fbcfe9a918bf7dbf9fd353f5b56bb0e02f7bdf69e
  - sha256:1c327fc62693aea603557acfcc40ff9f3dfbd5826d111e95b51f04a6e113cad8
checked_summary_ja: 対象リポジトリを変更せず、固定したGit基準とCopier更新元の組合せを隔離検証して証跡化する再利用可能なスキルを追加する。

## Context

Repeated downstream compatibility checks currently require an agent to reconstruct the safe update path, isolation boundary, validation selection, idempotence check, and evidence report from several policies and scripts.

The accepted proposal separates compatibility verification from a live update and requires exact Git identities, fail-closed ownership checks, downstream product validation, and an explicit unresolved result when the environment cannot complete the checks.

## Decisions

- Name the reusable Skill `verify-copier-update` and keep `verified`, `rejected`, and `blocked` bound to the sealed referents in the local advisory contract.
- Keep verification artifact-only outside both source repositories; a live update, commit, push, or external write remains outside this Skill.
- Reuse the generated update wrapper and validator instead of copying their ownership and migration rules into the Skill helper.
- Require callers to provide target-specific validation as JSON argv arrays and execute each array without a shell.
- Treat explicit template-task trust as a required execution input because Copier runs reviewed source tasks under `--trust`.
- Use bounded parent implementation because the inseparable slice must update deterministic validation-authority files; require an independent change review before the authoritative suite.

## Tasks

- [ ] Add the aligned root and generated Skill resources and executable verification helper.
- [ ] Register the bridge, ownership boundary, source inventory, smoke assertions, and changelog entry.
- [ ] Add deterministic isolated verification tests and review the complete diff against the primary invariant.
- [ ] Complete independent review, run focused and authoritative validation, archive the accepted plan, and commit the implementation.

## Validation Notes

- Decision audit and the user-approved proposal selected disposable verification, exact ref resolution, existing-validator reuse, full downstream validation, idempotence, and local bounded evidence.
- A local advisory referent contract fixed the Skill artifact, result conditions, and verification manifest before file authoring.
- Independent review found and parent remediation addressed validation-side worktree mutation, unsafe Copier launcher composition, dangling wrapper links, private scratch/source overlap, isolated source mutation, disposable commit hooks, original mutation result taxonomy, and the wrapperless real-Copier test lane.
- A second parent-direct remediation added original `HEAD`, refs, staged entries, normal status, and ignored-file identity snapshots with optional Git locks disabled.
- Re-review still found Medium gaps: staged-entry output does not preserve index flags such as `assume-unchanged` or `skip-worktree`, the snapshot does not preserve symbolic `HEAD` identity, and an ignored-file inspection error can copy an original absolute path into the manifest detail. These gaps can yield `verified` while the original Git index or checked-out branch state changed, or violate the bounded-manifest contract.
- The repository hard-replan rule therefore stopped execution before focused or authoritative validation. No implementation commit was created.
