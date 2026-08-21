# Integrate retirement Copier preservation

status: in_progress
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
implementation_mode: parent_direct
parent_direct_reason: template inventories and update validation are parent-owned validation authority under the current runner
primary_invariant: supported Copier updates preserve project-owned retirement configuration bytes while managing the generated specification and executable
replan_source: docs/plan/active/112-retire-merged-local-worktrees.md
replan_contract: docs/plan/replanned/contracts/112-retire-merged-local-worktrees.json
integration_gates:
  - plans 142, 144, 147, and 148 must be checked before Copier preservation integration starts
  - plan 146 must verify the combined successors against every source acceptance item
successor_plans:
  - docs/plan/active/142-define-local-git-retirement-policy.md
  - docs/plan/active/143-implement-read-only-retirement-scan.md
  - docs/plan/active/144-implement-revalidated-local-apply.md
  - docs/plan/active/145-integrate-retirement-copier-preservation.md
  - docs/plan/active/146-integrate-local-git-retirement.md
inherited_acceptance_digests:
  - sha256:27f9713e8bde723f894fc8c6ebf44f0daf5109f16c4502b16dddf1a9fbd92557
  - sha256:dab3be427e961b4584d9e634104eba538cd644eaf9e8657f25558acda39895cf
  - sha256:a24659ceb636d526e4ad01d26f86c6a0ba7a74cea99d59481fdd36229d35816f
write_scope:
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/copier-update.sh
  - tests/smoke.sh
context_files:
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
  - docs/plan/replanned/2026/08/16-31/143-implement-read-only-retirement-scan.md
  - docs/plan/checked/2026/08/16-31/147-complete-exact-root-retirement-scan.md
  - docs/plan/checked/2026/08/16-31/148-certify-exact-root-retirement-scan.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - references/validation.md
  - scripts/retire-merged-worktrees.py
  - template/.project-agent-workflow/ownership.yaml
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh
  - git diff --check
validation:
  - python3 scripts/check-copier-template.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Make generated project configuration safe-disabled by default; require each project to configure merge-target refs and protected local branches before scanning or applying, while the root repository explicitly protects `main` and `dev` and selects its local merge target.
  - Keep root and generated CLI files byte-identical, keep the root and generated specifications semantically aligned, and document the intentional difference between enabled root policy and safe-disabled generated project configuration.
  - Add the new managed files to Copier ownership and inventory checks while preserving project-owned retirement configuration byte-for-byte through supported Copier updates.
checked_summary_ja: 生成対象とproject-owned設定を分離し、Copier更新でretirement設定のbyte列を保持する。

## Context

This successor owns managed-file inventory, fresh generation, and supported Copier update evidence.

The generated specification and executable are template-owned, while the generated project's retirement configuration remains project-owned.

## Decisions

- Preserve customized project-owned configuration byte-for-byte through supported updates.
- Fail on conflicts, rejection files, or unclassified tracked-file deletion.
- Verify root/generated executable identity and specification alignment through deterministic checks.

## Tasks

- [ ] Extend Copier inventory and parity checks for the new managed files.
- [ ] Extend smoke generation assertions for safe-disabled defaults and managed outputs.
- [ ] Extend update scenarios to preserve customized retirement configuration bytes.
- [ ] Complete parent diff review, independent review, and focused validation before acceptance.

## Validation Notes

- Parent-direct implementation is required because inventory scripts and update tests are validation-authority paths rejected from worker candidates.
