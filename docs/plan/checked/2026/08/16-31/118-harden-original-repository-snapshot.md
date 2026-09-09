# Harden original repository state snapshot

status: checked
primary_invariant: compare the complete observable original Git repository state before and after isolated verification without mutating it during inspection
task_types:
  - planning_docs
  - security
  - skill_authoring
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: ordinary
implementation_ambiguity: low
write_scope:
  - .codex/skills/verify-copier-update/scripts/verify-copier-update.py
  - template/.project-agent-workflow/skills/verify-copier-update/scripts/verify-copier-update.py
  - tests/test-verify-copier-update.py
context_files:
  - AGENTS.md
  - .codex/skills/verify-copier-update/SKILL.md
  - .codex/skills/verify-copier-update/references/verification-contract.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
  - git diff --check
validation:
  - python3 tests/test-verify-copier-update.py
  - git diff --check
acceptance:
  - Require explicit downstream repository, template repository, immutable source selector, external output directory, target-specific validation argv, and template-task trust inputs; reject dirty, non-root, symbolic-link, missing-ref, source-layout, pre-v1, and force-style bypass conditions before executing the update.
  - Resolve and record exact target and source commit OIDs, clone both repositories without hard links into a disposable same-filesystem workspace, preserve a safe relative Copier source relationship, sanitize the child environment, and never change the original downstream or template worktree, Git refs, index, or ignored files.
  - Emit a bounded local verification manifest and separate command logs with verified only after every required check passes, rejected only after an observed update or invariant failure, and blocked when a prerequisite prevents completion; do not store credentials, environment values, or raw repository paths in the manifest.
  - Add deterministic verified, rejected, blocked, dirty-source, dirty-target, unsafe-output, invalid-validation-command, and original-repository-preservation coverage without embedding curiretas-account paths, versions, product commands, or credentials in the generic Skill.
replan_source: docs/plan/active/117-verify-copier-update-skill.md
replan_contract: docs/plan/replanned/contracts/117-verify-copier-update-skill.json
integration_gates:
  - plan 119 must retain and prove every source acceptance item after this snapshot invariant is committed
successor_plans:
  - docs/plan/active/118-harden-original-repository-snapshot.md
  - docs/plan/active/119-integrate-verify-copier-update-skill.md
inherited_acceptance_digests:
  - sha256:0cb43db13b4153482d507a327385b83829d6cd4e3e90955c6d17f788d29571b4
  - sha256:88220b0a100257d13495e09659be96f2e386ed7353bc1495cb60eb7b6f14b8e9
  - sha256:b8917301f15ee38f1b9f2d948627ffda18f95f08e5138a3b23fa3a0a06b05e10
  - sha256:308019cc71e5ea98d124915fbcfe9a918bf7dbf9fd353f5b56bb0e02f7bdf69e
checked_summary_ja: 元リポジトリのGit状態を変更せず、検証前後で完全に比較する処理を確立する。

## Decisions

- Snapshot the actual worktree-specific index bytes and every referenced split-index backing file with optional Git locks disabled.
- Reject baselines that use `assume-unchanged` or `skip-worktree`, because normal Git status cannot prove their tracked worktree bytes are unchanged.
- Snapshot raw tracked regular-file and symbolic-link bytes plus actual mode so clean filters and EOL normalization cannot hide original worktree changes; block Git submodule entries as an unsupported prerequisite.
- Block effective repository-local external clean/process filters before status inspection, disable system/global Git config inputs, and compare tracked raw identity before and after status to prevent snapshot observer effects.
- Stream tracked file hashing without the bounded Git-metadata file size limit; retain the limit only for HEAD, index, and split-index metadata files.
- Snapshot symbolic HEAD identity and ref symbolic targets in addition to resolved object IDs.
- Keep ignored-file identity bounded to metadata and symlink targets while detecting additions, deletions, and ordinary content writes.
- Replace filesystem exception details with bounded path-free messages before recording the manifest.
- Use bounded parent implementation because this inherited dirty slice changes its own validation authority; require independent read-only review before validation.

## Tasks

- [x] Add failing regressions for index flags, symbolic HEAD changes, and path-free manifest errors.
- [x] Implement complete original-state capture and byte-identical root/template helper updates.
- [x] Complete independent review with zero High or Medium findings.
- [x] Run focused and authoritative validation, record evidence, and commit this slice without staging integration-owned paths.

## Validation Notes

- This successor preserves the mapped source acceptance text exactly.
- Independent read-only review found zero High or Medium issues after two bounded parent remediation rounds. Dedicated include/includeIf mixed-case filter and tracked-symlink mutation tests remain Low-priority coverage opportunities; the corresponding implementation paths were reviewed as correct.
- Initial focused validation exposed three test-fixture defects: two incorrect test assumptions and one missing validation argument. The fixtures were corrected without changing the implementation contract.
- Focused validation passed: `python3 tests/test-verify-copier-update.py` (33 tests) and `git diff --check`.
- Authoritative validation passed once: `python3 tests/test-verify-copier-update.py` (33 tests) and `git diff --check`.
- Root and generated-template helper copies were byte-identical at acceptance.
