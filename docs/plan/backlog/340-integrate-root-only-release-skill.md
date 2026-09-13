# Integrate and verify the root-only release skill

status: backlog
primary_invariant: The structural regressions prove the skill's discovery metadata, reference resolution, routing, placement, and bounded Git examples, and never claim that word matching proves an agent made a correct release decision.
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
  - template_workflow
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
  - {"evidence":"tests/test-validation-tools.py already imports bounded test domains from tests/validation_tools/ and is run by the mandatory lint, so the new module needs no second entrypoint and no new authoritative gate.","kind":"existing_mechanism"}
  - {"evidence":"tests/validation_tools/support.py already exposes ROOT and the existing domains already build temporary fixtures and isolated Git repositories, so the structural regressions reuse established patterns.","kind":"existing_mechanism"}
completion_conditions:
  - A release-skill regression module runs through the existing validation-tools aggregate entrypoint, checks metadata, local reference resolution, routing, absence of generated placement, and bounded Git-ref examples against isolated repositories, and rejects missing metadata and broken references in temporary fixtures.
  - The root source inventory registers the new test module, and the existing root and template alignment and README and change-log version checks pass unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:3ee69e9486a3b95846d341b330c14f359ce1c35bf0f7682f17b0ea5b2d803dc9","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:02030e3d77aefafcd953d9de2503168c9cd483a799611aba0a057aa6518d4c30","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - tests/validation_tools/release_skill.py
  - tests/test-validation-tools.py
  - scripts/project_workflow/copier_inventory.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - scripts/check-copier-template.py
  - references/template-development.md
  - tests/validation_tools/support.py
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
checked_summary_ja: リリーススキルの構造的回帰を既存の検証系へ組み込み、受け入れを確定する

## Decisions

- Keep the regressions structural. They prove artifact contracts and that the documented Git examples run; they never prove instruction quality, which stays an independent review judgement.
- Import the module exactly once into the existing aggregate entrypoint. Do not add a second test entrypoint or a new authoritative validation gate.
- Check that existing external URL targets and stable version pins are unchanged, and perform no network call and no operation on a live ref.

## Tasks

- [ ] Add tests/validation_tools/release_skill.py with structural tests that read the skill frontmatter, require exactly name and description, require the folder name to match, and require the metadata file to supply display name, short description, and default prompt.
- [ ] Resolve every repository-local Markdown link in the skill body, the runbook, and both routing documents, and assert that both routing documents reach the runbook.
- [ ] Assert that the skill is absent from template/.agents/skills/ and template/.project-agent-workflow/skills/, so a later change cannot silently turn it into generated content.
- [ ] Exercise the detection side in temporary fixtures: missing frontmatter, a broken local reference, and an unexpected frontmatter field must each be observable rather than silently accepted.
- [ ] Validate the runbook's Git examples: every push example must name one exact refs/heads or refs/tags target, no write example may fan out or force, and the annotated tag example must run against an isolated temporary repository and dereference to the expected commit.
- [ ] Assert that the README external link targets and the current stable-version copy example are unchanged, and perform no network call.
- [ ] Import the three test classes exactly once in tests/test-validation-tools.py and register tests/validation_tools/release_skill.py in SOURCE_REQUIRED in scripts/project_workflow/copier_inventory.py.
- [ ] Run python3 tests/test-validation-tools.py and python3 scripts/check-copier-template.py, then the authoritative suite once, and have an independent read-only reviewer walk preparation-only, normal publication, blocked downstream, existing-tag mismatch, tag-CI failure, and interrupted-write scenarios against the authored skill before acceptance.
