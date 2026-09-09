# Define local Git retirement policy and configuration

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
  - referent_first
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: ordinary
implementation_ambiguity: low
implementation_mode: parent_direct
parent_direct_reason: every changed policy and template path is parent-owned validation authority under the current runner
primary_invariant: generated retirement policy remains safe-disabled until configured while the root policy explicitly selects local refs and protected branches
replan_source: docs/plan/active/112-retire-merged-local-worktrees.md
replan_contract: docs/plan/replanned/contracts/112-retire-merged-local-worktrees.json
integration_gates:
  - plan 143 must consume the policy and configuration contract without broadening local effects
  - plan 146 must verify the combined successors against every source acceptance item
successor_plans:
  - docs/plan/active/142-define-local-git-retirement-policy.md
  - docs/plan/active/143-implement-read-only-retirement-scan.md
  - docs/plan/active/144-implement-revalidated-local-apply.md
  - docs/plan/active/145-integrate-retirement-copier-preservation.md
  - docs/plan/active/146-integrate-local-git-retirement.md
inherited_acceptance_digests:
  - sha256:27f9713e8bde723f894fc8c6ebf44f0daf5109f16c4502b16dddf1a9fbd92557
  - sha256:31b60f932bf07f6ee1589f786f849e78eebbddec7625a95690026e5aa29f7bce
  - sha256:dab3be427e961b4584d9e634104eba538cd644eaf9e8657f25558acda39895cf
  - sha256:3688d2080c082315da128caac3e8acf11b8dab8aa552a4490a66c34d0c2277aa
write_scope:
  - AGENTS.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/git-retirement.yaml
  - docs/agent/spec-index.yaml
  - scripts/check-root-agent-policy.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_RETIREMENT.md
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - template/.project-agent-workflow/ownership.yaml
  - template/docs/agent/git-retirement.yaml.jinja
context_files:
  - docs/plan/replanned/2026/08/16-31/112-retire-merged-local-worktrees.md
  - template/.project-agent-workflow/docs/agent/SPEC_FILE_MANAGEMENT.md
  - template/.project-agent-workflow/docs/agent/SPEC_GIT_WORKFLOW.md
  - references/validation.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
acceptance:
  - Make generated project configuration safe-disabled by default; require each project to configure merge-target refs and protected local branches before scanning or applying, while the root repository explicitly protects `main` and `dev` and selects its local merge target.
  - Keep scheduled automation read-only by permitting scan and report generation only; require a current explicit operator action for every local apply.
  - Keep root and generated CLI files byte-identical, keep the root and generated specifications semantically aligned, and document the intentional difference between enabled root policy and safe-disabled generated project configuration.
  - Keep provider-assisted squash or rebase integration evidence, remote branch deletion, and actual stale-worktree metadata pruning outside this implementation; require separate active plans and applicable authorization before adding them.
checked_summary_ja: localのGit worktreeとbranchを安全に整理するための方針、設定、routing、ownership境界を定義する。

## Context

This successor owns the policy and reusable configuration boundary extracted from source plan 112.

The root configuration is enabled for the repository's local refs, while generated configuration must remain disabled until a generated project explicitly chooses its refs and protected branches.

## Decisions

- Keep host-specific absolute worktree roots out of reusable configuration.
- Keep scheduled behavior read-only and require an explicit current operator action for local removal.
- Keep provider evidence, remote deletion, force deletion, and destructive pruning outside this successor.

## Tasks

- [x] Add root and generated specifications with aligned behavior and the intentional root/generated configuration difference.
- [x] Add root and generated project-owned configuration with safe generated defaults.
- [x] Route cleanup requests through the specification and classify new files in ownership policy.
- [x] Add deterministic root-policy routing checks for the new specification.
- [x] Complete parent diff review, independent review, and focused validation before acceptance.

## Validation Notes

- Parent-direct implementation is required because all changed policy and template files are validation-authority paths rejected from worker candidates.
- The existing ownership rules classify `.project-agent-workflow/**` as Copier-managed and `docs/agent/**` as seeded project-owned, so no overlapping ownership entry was added.
- Independent review round 1 found two Medium issues in the generated command path and apply-stage wording plus one Low checker weakness; the bounded remediation corrected all three.
- Independent review round 2 reported no findings.
- Focused validation passed: `python3 scripts/check-root-agent-policy.py`; `git diff --check`.
- Authoritative validation passed once with the same plan validation commands.
- Parent-owned execution ledger: `/home/rectaris/tmp/gakumasu-project/plan-execution-ledgers/142-define-local-git-retirement-policy.json`.
