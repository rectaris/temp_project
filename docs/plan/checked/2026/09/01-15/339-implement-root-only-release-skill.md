# Implement the root-only release skill and its parity exemption

status: checked
primary_invariant: A root-only skill exists only when the parity check names it explicitly; every unnamed root skill still requires its generated counterpart, and generated content and external-effect authority stay unchanged.
replan_source: docs/plan/active/336-add-project-release-skill.md
replan_contract: docs/plan/replanned/contracts/336-add-project-release-skill.json
integration_gates:
  - The root-only release skill, its routing, its structural regressions, and the named parity exemption are verified together against the source acceptance item.
successor_plans:
  - docs/plan/active/339-implement-root-only-release-skill.md
  - docs/plan/active/340-integrate-root-only-release-skill.md
inherited_acceptance_digests:
  - sha256:f20020c6f8c1338cddb6b7c0b935c933a19203bf280403b7b5016f8e9765d9c6
task_types:
  - skill_authoring
  - planning_docs
  - user_communication
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"SPEC_SKILL_AUTHORING.md Placement already permits root-only workflow skills under .codex/skills/, so the exemption restores agreement between the specification and the check rather than adding a new allowance.","kind":"existing_mechanism"}
  - {"evidence":"check-copier-template.py already compares the root and generated managed skill inventories as two directory listings, so a named exemption is one bounded set subtraction at that single comparison.","kind":"existing_mechanism"}
  - {"evidence":"copier_inventory.py already registers every root skill asset in SOURCE_REQUIRED, so registering three more files repeats an existing entry pattern.","kind":"mechanical_transformation"}
completion_conditions:
  - The root-only release-project skill carries valid discovery metadata and resolves its runbook, and README and the template development guide route to that runbook while preserving external link targets and current stable-version anchors.
  - check-copier-template.py admits exactly the named root-only skills and still fails for any other root skill that has no generated counterpart, leaving every generated inventory unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:47699b805ca931e674b286401a461a90c8ae497ae37403e44701e2cab1eefec8","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:2dd3558edf19dfe8771e5bb0deeba9a497a07a954c4635ed2dd55d6a9a2c770b","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - .codex/skills/release-project/SKILL.md
  - .codex/skills/release-project/agents/openai.yaml
  - .codex/skills/release-project/references/workflow.md
  - README.md
  - references/template-development.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - scripts/lint-project-workflow.sh
  - docs/plan/checked/2026/09/01-15/334-release-v148-for-ownership-record-retirement.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - references/validation.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The repository provides a discoverable root-only release skill with a linked, structurally validated runbook for preparation and authorized publication, consistent with current release references and leaving generated content and existing external-effect authority unchanged.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f20020c6f8c1338cddb6b7c0b935c933a19203bf280403b7b5016f8e9765d9c6","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: root 専用のリリーススキルと、それを許す名指しの整合例外を実装する

## Decisions

- The source plan stopped because a root-only skill cannot exist while check-copier-template.py requires identical root and generated skill inventories. The owner authorized reconstructing the work as Tier 2 so the exemption is in scope.
- Name the exempt skills explicitly rather than dropping or weakening the parity comparison. An unnamed root skill without a generated counterpart must still fail, because parity is what keeps a reusable skill from silently becoming root-only.
- Keep every generated inventory, discovery bridge, and external-effect authority unchanged. This plan adds no generated counterpart, no release executor, no CI job, and no versioning rule.

## Tasks

- [x] Create the three root skill files: a concise SKILL.md whose frontmatter carries only name and description and whose description states the preparation, publication, and interrupted-release triggers and excludes downstream Copier adoption and application deployment; agents/openai.yaml with display name, short description, and default prompt; and references/workflow.md as the single reference layer.
- [x] Write the runbook to resolve the requested phase, previous stable tag, candidate commit, intended version, source, integration and publication refs, and whether a pull request or GitHub Release was requested, deriving each from live state rather than a past release plan, and to end preparation-only work in an explicitly bounded preparation report.
- [x] Route version selection to the README criteria and to copier.yml migration version constraints, state that the pyproject.toml version is not the Copier release version, and require an owner decision with concrete impact when the criteria do not select one version.
- [x] Document preparation inside a task worktree: review the prior-tag diff, preserve unrelated product changes and historical plan records, date the change-log section while retaining the 未リリース marker, update only current README anchors, preserve external link targets, and confirm agreement with check-copier-template.py instead of a textual replacement.
- [x] Document release validation from the current development guide and CI, require the release-relevant Copier and workflow checks to run, name any skipped or unavailable check, bind each result to the exact commit it ran against, and state that a pull-request head result does not carry to a merge or tag commit.
- [x] Document verify-downstream-baselines.py for the exact candidate source OID and every configured baseline with evidence outside the repository, read result and reason per baseline, stop tagging on a blocked result, and forbid cleaning a downstream checkout, inventing a product command, dropping a baseline, or inferring a waiver.
- [x] Document finishing the task worktree through manage-plan-worktrees.py before any remote operation, then the requested pull-request path with exact head and base, the external-service gate, the required merge without an automatic merge step, and establishing the exact remote publication OID that contains the preparation commit.
- [x] Document separate exact authorization for branch push, tag push, pull-request publication, and GitHub Release publication, and replace the broad README --tags example with bounded exact-ref examples while preserving external link targets.
- [x] Document tag creation only after the candidate and downstream checks: inspect local and remote tag existence, create an annotated tag at the verified publication OID, confirm the dereferenced target, resume from a matching existing tag, stop on a different target, and never force-move or delete a published tag.
- [x] Document post-tag CI inspection for the exact tag commit before a requested GitHub Release, using plan 092 as evidence that preparation can succeed while the tag context fails, and require preserving a failed published tag while withholding the success claim and the Release.
- [x] Document interruption recovery by reading exact remote refs, pull-request and merge state, CI state, and Release state before retrying an uncertain write, reusing already matching operations, stopping on mismatches, and reporting preparation commit, publication OID, tag target, CI, downstream limitations, and Release URL or explicit non-publication separately.
- [x] Add the named root-only exemption to the skill inventory comparison in check-copier-template.py so the comparison subtracts exactly the named skills, and confirm by inspection that an unnamed root skill without a generated counterpart still fails.
- [x] Register the three root skill assets in SOURCE_REQUIRED in scripts/project_workflow/copier_inventory.py and leave GENERATED_REQUIRED and every generated inventory untouched.

## Validation Notes

- `python3 scripts/check-copier-template.py` passes with the named exemption in place.
- The negative behaviour was checked directly: an empty unnamed root skill directory still fails the inventory comparison, and the failure disappears only when that directory is removed. The exemption subtracts exactly the named skills.
- `python3 tests/test-validation-tools.py` passes with 302 tests. The release-skill regressions themselves belong to plan 340, so this run proves that the skill and the exemption break nothing that already existed.
- `python3 scripts/validate-changes.py --all`, `./scripts/lint-project-workflow.sh` and `./tests/smoke.sh` all exit 0.
- The source plan stopped because this exemption edits validation authority, which its Tier 1 write scope excluded. The reconstruction records that as the reason; no source acceptance item was changed.
