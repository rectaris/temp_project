# Resolve PR43 conflicts while preserving both accepted public features

status: in_progress
primary_invariant: PR43 retains every accepted scope-diagnostic and current public-base input-bundle behavior, distribution entry and history while incorporating the exact live public dev ancestor without force push, private-dev history or new execution authority.
task_types:
  - template_workflow
  - planning_docs
  - security
  - task_worktrees
  - external_services
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Direct live refs give public head56f6e93 and devb8fdfd4, while PR base metadata still reportsCDF. Three-tree inspection against liveb8f identifies four conflict paths: changelog, checked index, distribution inventory and real-update source inventory.","kind":"reproduced_defect"}
  - {"evidence":"Both branches shareCDF; upstreamb8f adds accepted parent-authority inputs and archives388. Preserve its exact file/mode additions and the public diagnostic files; resolve four overlaps as ordered unions within their existing categories.","kind":"mechanical_transformation"}
  - {"evidence":"Existing full semantic suite, real Copier fresh/update fixture, public diagnostic consumer hook and upstream parent-authority CLI fixture exercise both installed command families. Existing normal managed publication and nonforce Git push preserve accepted ancestry.","kind":"existing_mechanism"}
completion_conditions:
  - The integrated root input-bundle CLI materializes and verifies exact accepted inputs, rejects corruption without deleting retained evidence and keeps execution_authorized and member_write_admitted false.
  - The retained public diagnostic-authoring and input-bundle behavioral regression suites pass together with existing cases intact and unchanged safety and ordinary-use contracts.
  - Actual fresh and supported updated installed consumers exercise both retained command families while preserving project-owned artifacts.
completion_witness_map:
  - {"condition_sha256":"sha256:1f3f68c15612b92a67e0259ec39746e7a62874bf54148f5c7c731e2d29db5aa9","witness":"python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py"}
  - {"condition_sha256":"sha256:c2d7ad97fdbc73a99bc59ca806670b0cecd0075c81cdb2fe09bde16445b4d8ae","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:c9ed6c81affd39d411c661a5d2ce84d6af905f3ef2bfd7345fa499becf8ff9a3","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - CHANGELOG.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/388-publish-parent-held-git-input-foundation.md
  - docs/plan/checked.md
  - docs/plan/checked/2026/10/16-31/388-publish-parent-held-git-input-foundation.md
  - docs/plan/plan.md
  - docs/research/review-execution-and-evaluation-proposal.md
  - scripts/check-copier-template.py
  - scripts/parent-authority.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/project_workflow/parent_authority.py
  - scripts/project_workflow/process_runtime.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/parent-authority.py
  - template/.project-agent-workflow/scripts/parent_authority.py
  - template/.project-agent-workflow/scripts/process_runtime.py
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/fixtures/orchestration/parent-authority-cli.py
  - tests/smoke.sh
  - tests/test-validation-tools.py
  - tests/validation_tools/parent_authority.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/project_workflow/worktree_guard.py
  - docs/agent/git-retirement.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The integrated actual root input-bundle CLI verifies pinned inputs, refuses corruption while retaining evidence, and keeps execution and member admission unauthorized.
  - The complete existing public diagnostic-authoring and input-bundle semantic regressions pass together without deleting or weakening cases, changing ordinary contracts or expanding safety authority.
  - Actual new generated and supported updated distributions exercise both retained command families and preserve project-owned code, policy, configuration and history.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:2d8c96379e626efe62b7a0eff62a1bd8f5885708897276853754c7868a5455b0","stage":"focused","witness":"python3 tests/fixtures/orchestration/parent-authority-cli.py scripts/parent-authority.py"}
  - {"acceptance_sha256":"sha256:cc50775a6544e5f11dc8db8055bea7ba1dd3ed31e5dde05510c9ed7e77d34a69","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:6ba659e47447fa7a0737ad8bd43c069307585d683ebd05195e187598572f287d","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 公開devとPR43の変更を保持して競合を解消した。

## Decisions

- Use live devb8fdfd4c4785077837311e2b90f276736619f5cf and existing PR head56f6e93c9f6c6e406bb08c4284cfcec908b10885, not stale pull-baseCDF or private dev. Keep both histories through a normal merge into the PR branch; do not rebase or force push.
- Tier2 is conservative because accepted upstream changes touch validation/delivery and lifecycle records. It does not introduce new authority or new feature requirements. Enumerate every upstream delta path; manual conflict resolution is limited to the four observed files plus a factual changelog note.
- Union registrations within existing categories, preserve all existing membership and exact root/template bytes/modes. Retain PR411/412 checked records, current dev checked388 and existing deferred418. Upstream deletion of active388 is its already accepted relocation, not an agent-authored deletion or re-completion.
- Parent owns authoring, integration, immutable exact-source review, all existing validation, acceptance and normal worktree publication. New plan only starts from its normally published active bytes. Preserve adopted primary necessity-1, old stopped sources, unknown consumption and canonical reviewer registry; import no private policy or history.
- Keep both meaningful existing suites and real CLI/installed consumers. No new tests of source wording, forwarding or registration echoes. Resolve every actual High/Medium and keep authoritative failure diagnosis gates; no unchanged authority is reopened or new review-count ceiling invented.
- After exact acceptance, normally complete the same plan with protected summary/conditions/maps unchanged, publish only exact scoped PR head and verify direct remote refs, latest current-head CI and mergeability. No merge into dev/main, release, credentials/payment/model/provider changes, controller adoption or source478 operation.
- Product acceptance binds each actual CLI/semantic/installed claim to its own earliest declared command. Parent separately verifies exact merge ancestry, four-path ordered unions, source/mode retention and plan-history relocation before local publication, and direct remote refs/mergeability/current-headCI after ordinary push. Do not claim the Copier command proves Git history or a future external effect; the owner conflict-resolution outcome remains mandatory in the final task.

## Tasks

- [ ] Publish checked exact-scope authoring before integration.
- [ ] Merge exact live public base into the PR task, resolve only the four observed overlaps while retaining both sides and inspect automatic merges and upstream plan relocation.
- [ ] Exercise both actual root/installed consumer families, all full focused and unchanged mandatory checks; obtain independent exact-target review and parent acceptance.
- [ ] Normally publish and close this same plan preserving protected fields, retire exact task/branch, refresh exact GitHub gates, normally push only PR43 and verify current direct refs/CI/conflict resolution.

## Validation Notes

- Owner explicitly requested repair of PR43 merge conflicts. Current live base is read independently through git/ref/heads/dev; pull metadata baseCDF is not used as current truth.
- Read-only three-tree artifact197 retains concrete conflict evidence; no candidate or merged code has been accepted. Root source primary policy necessity-1/controller7501 is preserved; public policy absence remains absence.
- Authoring own-env preparation initially refused before sync, retained exact task/record, and prescribed own locked sync194 succeeded. No check is weakened and no formal validation failure or execution receipt is fabricated.
- First unpublished authoring target1a190 receives source review148. Parent confirms its Medium: installed fixture cannot witness future publication or all root behavior; split technical claims by existing actual command, retaining the entire owner Git/remote outcome in parent publication duties. Claimed High duplicate is factually unsupported: lines44/45 are distinct parent-authority.py entrypoint and parent_authority.py library; all22scopepaths are unique. Preserve original patch/review/unknowns and obtain independent clearance of the revised unpublished plan; no implementation or public admission has started.
- Original authoring203 lint and smoke finish0 on the untouched original draft. They remain old-target evidence only. Official nonwriting check207 verifies the revised correspondence; its next-id414 is not allocated or written. Parent revises only this existing unpublished413 draft, with exact derived condition/acceptance digests and no new plan, successor or execution budget. Fresh mandatory checks and independent clearing assessment remain required before publication.
