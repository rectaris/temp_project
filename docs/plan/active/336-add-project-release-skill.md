# Add a root release skill grounded in recorded release work

status: in_progress
primary_invariant: The release skill guides the exact requested release phase through existing policy and validation, without treating preparation, invocation, or historical publication permission as authority or proof of publication.
task_types:
  - skill_authoring
  - planning_docs
  - user_communication
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"SPEC_SKILL_AUTHORING.md permits root-only workflow skills. Existing root skills supply the concise SKILL.md, agents/openai.yaml, and direct references pattern; generated counterparts are required only for reusable generated-project content.","kind":"existing_mechanism"}
  - {"evidence":"check-copier-template.py already checks README/CHANGELOG version agreement; verify-downstream-baselines.py, check-external-service-policy.py and manage-plan-worktrees.py already provide the needed release checks and effect boundaries.","kind":"existing_mechanism"}
  - {"evidence":"Checked plans 084, 090, 092, 110, 295, 290, 329 and 334 record preparation, exact tag targets, CI failures, and downstream limitations. tests/test-validation-tools.py already imports bounded test domains and is run by mandatory lint.","kind":"existing_mechanism"}
completion_conditions:
  - The root-only release-project skill has valid discovery metadata and resolves its runbook and current policy/tool references without adding a generated-project skill.
  - The README and development guide route to the release runbook, retain current stable-version examples and external URL targets, and demonstrate only exact branch/tag targets.
  - The release-skill structural regressions run through the existing validation-tools aggregate and reject missing metadata, broken local references, and accidental generated-skill placement.
  - The root source inventory registers the new skill assets and test module, and existing root/template alignment and README/CHANGELOG current-version checks pass.
completion_witness_map:
  - {"condition_sha256":"sha256:a57f580d587328a96f54d2cfb80743ef1e3d04576b64eebebc82c797c7b9cca4","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:4d2bd4537a33ec1ac78c3391a4ad64928aad6896dfea71e363c07dc9db2b1218","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:be211de0911c5f54763765532ab95dc1e156c940412f087ccbb833e339fe9a64","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:5d4ca99424144ae2d2bcdd64bd113d18960ac5ae24b47f2edb8e2faba477240b","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/release-project/SKILL.md
  - .codex/skills/release-project/agents/openai.yaml
  - .codex/skills/release-project/references/workflow.md
  - README.md
  - references/template-development.md
  - tests/validation_tools/release_skill.py
  - tests/test-validation-tools.py
  - scripts/project_workflow/copier_inventory.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - CHANGELOG.md
  - .github/workflows/ci.yml
  - docs/downstream-baselines.yaml
  - docs/agent/external-services.yaml
  - scripts/verify-downstream-baselines.py
  - scripts/check-external-service-policy.py
  - scripts/manage-plan-worktrees.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - .codex/skills/verify-copier-update/SKILL.md
  - docs/plan/checked/2026/08/01-15/084-prepare-release-v141-pr.md
  - docs/plan/checked/2026/08/01-15/090-release-v142.md
  - docs/plan/checked/2026/08/01-15/092-release-v143-tag-fixture.md
  - docs/plan/checked/2026/08/01-15/110-release-v144.md
  - docs/plan/checked/2026/09/01-15/295-release-v145-for-downstream-verification.md
  - docs/plan/checked/2026/09/01-15/290-release-v146-for-downstream-archive-reading.md
  - docs/plan/checked/2026/09/01-15/329-release-v147-for-downstream-improvement-flow.md
  - docs/plan/checked/2026/09/01-15/334-release-v148-for-ownership-record-retirement.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - references/validation.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The repository provides a discoverable root-only release skill with a linked, structurally validated runbook for preparation and authorized publication, consistent with current release references and leaving generated content and existing external-effect authority unchanged.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f20020c6f8c1338cddb6b7c0b935c933a19203bf280403b7b5016f8e9765d9c6","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 過去のリリース手順を基に、このリポジトリ専用のスキルを作る

## Decisions

- The owner instruction is: 提案の方針かつ、過去のリリース作業から必要な作業手順をプランを作成せよ。 This plan implements the accepted skill approach; this authoring task does not execute it or perform a release.
- release-project is the root-only skill that guides preparation and authorized publication of this template repository through existing policy and tools. Keep SKILL.md concise, add normal discovery metadata, and put conditional detail in its directly linked references/workflow.md.
- Apply the accepted root-only scope under SPEC_SKILL_AUTHORING.md Placement: no generated counterpart or discovery bridge is added because this runbook releases the template publisher itself. This is an intentional placement difference, not a general parity exemption. Keep reusable policies, tools, template inventories and generated behavior unchanged.
- Keep Tier 1 with one acceptance item: this is bounded guidance and structural regression coverage under existing validation commands, not a new release executor, release policy, CI job, version scheme, or external authorization mechanism. Keep current root/template alignment checks intact.
- Treat current repository policy and tools as normative. Checked releases are bounded historical evidence, not reusable permission or proof of post-plan publication. Do not copy an old exception or manual recovery into the normal release path.
- Keep deterministic release checks in existing scripts/tests. New test code verifies structural contracts and executable examples; semantic scenario review remains independent evidence and must never be claimed as proved by word matching.
- Use bounded parent implementation for the inseparable guide/test/inventory change if the runner refuses these authority-sensitive context surfaces; retain applicable independent review and acceptance gates. Do not delegate protected files to a writable worker.

## Tasks

- [ ] Create the three root skill files and link the runbook from README and references/template-development.md. Describe triggers for preparation, publication, and interrupted-release inspection, and exclude downstream Copier adoption and generic application deployment. Preserve normal implicit discovery and all existing policy precedence.
- [ ] Write the first runbook step to identify the requested phase, previous stable tag, candidate commit, intended version, source/integration/publication refs, and whether a PR or GitHub Release was requested. Derive live values rather than copying historical dev/main/version assumptions; preparation-only work ends with an explicitly bounded preparation report.
- [ ] Route version selection to README criteria and inspect migration version constraints in copier.yml. Explain that the pyproject.toml placeholder is not the Copier release version. When history and the current criteria do not justify one version, present the concrete impact for an owner decision rather than inferring a new versioning policy.
- [ ] Document preparation in a task-bound worktree: review the prior-tag diff, preserve unrelated product changes and historical plan records, date the CHANGELOG release section while retaining 未リリース, update only current README version anchors, and preserve external URL targets. Reuse check-copier-template.py instead of a broad textual replacement.
- [ ] Document release validation from the current development guide and CI: dependency setup, version alignment, lint, smoke, hooks, Copier copy/update paths, whitespace and current minimum-compatibility checks. Require release-relevant Copier/actionlint checks to run, name skipped or unavailable checks, and bind results to exact tested commits. Reuse valid evidence only for unchanged tested input and command; PR-head success alone cannot prove a changed merge/tag commit.
- [ ] Document verify-downstream-baselines.py for the exact candidate source OID and every configured baseline, with evidence outside the repository as its command requires. Read the actual result and reason per baseline: target_dirty or another blocked result stops tagging; verified without product validation proves only the recorded checks. Never clean a downstream checkout, invent product commands, drop a baseline, or infer a waiver from plans 290/329.
- [ ] Document finishing and publishing the preparation task locally through manage-plan-worktrees.py before remote publication. For a requested PR path, prepare the exact head/base and body, apply the current external-service gate, wait for the required merge, and establish the exact remote publication-branch OID containing the preparation commit. Do not introduce an automatic merge operation.
- [ ] Document separate exact authorization for branch push, tag push, PR publication and GitHub Release publication using SPEC_EXTERNAL_SERVICES.md and mcp-ops. Reuse applicable existing user authorization; ask only for genuinely missing exact authorization after the proposed target and payload are reviewable. Replace the broad README --tags example with bounded exact-ref examples, preserving external link targets.
- [ ] Document tag creation only after the required candidate/downstream checks: inspect local and remote tag existence, use an annotated tag at the verified publication OID, and confirm the dereferenced tag target. An existing matching tag is evidence to inspect and resume from, not permission to recreate it; a different target stops the operation. Never force-move or delete a published tag.
- [ ] Document post-tag CI inspection for the exact tag commit before requested GitHub Release publication. Use plan 092 as evidence that successful preparation can precede tag-context failure. Preserve a failed published tag, withhold a success claim and Release publication, and route diagnosis/correction through current policy rather than silently selecting or publishing another version.
- [ ] Document interruption recovery by reading exact remote refs, PR/merge state, CI and Release state before retrying an uncertain write. Reuse already completed matching operations, stop on mismatches, and keep the final report separate for preparation commit, publication OID, tag target, CI, downstream result limitations, and Release URL or explicit non-publication.
- [ ] Add tests/validation_tools/release_skill.py and import its tests exactly once in tests/test-validation-tools.py. Parse metadata and local Markdown links, exercise valid and broken references/missing metadata in temporary fixtures, check absence of generated placement, and validate bounded Git-ref examples against isolated Git repositories. Check existing external URL targets and stable pins remain unchanged; do not perform network calls or alter live refs.
- [ ] Register the new root skill assets and test module in SOURCE_REQUIRED in scripts/project_workflow/copier_inventory.py so existing inventory and syntax checks cover them. Leave GENERATED_REQUIRED and all generated inventories untouched. Run both focused commands; do not add a second test entrypoint or a new authoritative gate.
- [ ] Before acceptance, have a read-only independent agent walk through preparation-only, normal requested publication, blocked downstream, existing-tag mismatch, tag-CI failure, and interrupted-write scenarios against the authored skill and minimal synthetic evidence. Permit no external writes. Require correct next action and bounded completion claims in each scenario; retain prompts, outputs and parent judgment locally. Add one reviewer-chosen holdout and a negative trigger for downstream adoption. Fix demonstrated gaps without weakening policy.
- [ ] Use skill-creator validation when available and the required repository commands. Record structural results separately from the independent walkthrough, compare against the same scenarios using the pre-skill docs when evaluating improvement, and do not claim measured time savings without measurements. Commit the accepted scoped change and publish its task worktree; no release, tag, push, or GitHub Release is part of implementing this skill.

## Validation Notes

- Authoring evidence: checked 334 records v1.4.8 preparation at the current local baseline. No remote tags, PRs, CI runs or GitHub Releases were queried in this planning task; none are assumed successful.
- The focused test witness proves the structural artifact conditions only. Independent scenario outcomes in Tasks are required to assess instruction quality; a passing metadata/link test is not evidence that an agent made correct release decisions.
