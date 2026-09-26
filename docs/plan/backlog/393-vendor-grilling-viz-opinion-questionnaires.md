# Vendor grilling-viz questionnaires and route opinion requests through submitted answers

status: backlog
primary_invariant: An agent that asks for the user's opinion acts only on answers the user submitted, and a questionnaire update never discards or silently reuses an answer whose question changed.
task_types:
  - template_workflow
  - skill_authoring
  - user_communication
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The locally installed grilling-viz renderer generated a standalone three-question HTML; Node checks passed for schema validation, inline scripts, initially empty answers, serialization, restoration and copied text. render.mjs imports only node: built-ins.","kind":"bounded_prototype"}
  - {"evidence":"The local copy exposes --inspect, --if-match SHA256 refusal of a changed file, and a generated documentId kept across updates, which are the answer-retention mechanisms this plan tests. It has no LICENSE or agents/openai.yaml, and its SKILL.md names a grilling skill that is not installed.","kind":"existing_mechanism"}
  - {"evidence":"Checked plan 107 vendored natural-japanese with provenance notes, mirrored managed copies, a generated bridge and full Copier registration; the same file set applies here.","kind":"existing_mechanism"}
completion_conditions:
  - The vendored renderer matches upstream mathbullet/skills commit 5ab997fcb8a80da4938bacb0a86cbd568e1018a7 byte for byte, carries its MIT LICENSE, and references/upstream.md records the source path and SHA-256 of every vendored file and every local adaptation.
  - GrillingVizTest renders a standalone questionnaire with choices and free text, rejects malformed question data, starts with empty answers, keeps documentId across an update, and refuses an overwrite without a matching --if-match digest.
  - The root and generated SPEC_USER_COMMUNICATION state that an agent seeking an opinion offers a questionnaire, waits for the pasted answers, and treats a missing answer as no decision, and the root policy check asserts those statements.
  - Root and generated grilling-viz skills and the generated bridge stay aligned, and every new managed file is registered and passes the template checker.
  - A real Copier update installs the skill and preserves project-owned configuration and existing workflow behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:370af81aa7c52b26e889192c4d95cf8a4b47c5f9a7baba1f47874c8f63e0e8ce","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:07760272549b852b53c1efba929a6ac18b7d6dcfb55e2d3815aeb75d40fa891f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:6a13c81596a734279ae53c889ebee4fa1b449f07a743bd6ea2ae9c3bc1cf95a2","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:106a0ec3b2f9baf53a558302e11346d7bd3652a0f909fca0d11e0f748617723b","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:56ec5d5842bf717cced3ce54e398202cef7a141f733052b85efbc525fb0f32d6","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - .codex/skills/grilling-viz/SKILL.md
  - .codex/skills/grilling-viz/agents/openai.yaml
  - .codex/skills/grilling-viz/references/upstream.md
  - .codex/skills/grilling-viz/LICENSE
  - .codex/skills/grilling-viz/scripts/render.mjs
  - .codex/skills/grilling-viz/scripts/answer.js
  - .codex/skills/grilling-viz/scripts/components.js
  - .codex/skills/grilling-viz/design-system/tokens.css
  - .codex/skills/grilling-viz/design-system/components.css
  - .codex/skills/grilling-viz/design-system/component-samples.html
  - template/.project-agent-workflow/skills/grilling-viz/SKILL.md
  - template/.project-agent-workflow/skills/grilling-viz/agents/openai.yaml
  - template/.project-agent-workflow/skills/grilling-viz/references/upstream.md
  - template/.project-agent-workflow/skills/grilling-viz/LICENSE
  - template/.project-agent-workflow/skills/grilling-viz/scripts/render.mjs
  - template/.project-agent-workflow/skills/grilling-viz/scripts/answer.js
  - template/.project-agent-workflow/skills/grilling-viz/scripts/components.js
  - template/.project-agent-workflow/skills/grilling-viz/design-system/tokens.css
  - template/.project-agent-workflow/skills/grilling-viz/design-system/components.css
  - template/.project-agent-workflow/skills/grilling-viz/design-system/component-samples.html
  - template/.agents/skills/grilling-viz/SKILL.md
  - tests/validation_tools/grilling_viz.py
  - tests/fixtures/grilling-viz/questions.json
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/ownership.yaml
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/assert-generated-semantics.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/test-validation-tools.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/01-15/107-complete-natural-japanese-copilot.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - references/orchestration.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Agents seeking user opinions generate standalone grilling-viz questionnaires with choices and free text, retain answers across safe updates and use submitted answers rather than assuming consent.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a2f14e060b3c4ae46698f84a94f3f684a2b746f1ab757c6830c60e7715048548","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: grilling-vizを取り込み、利用者の意見を選択肢と自由入力の質問票で集め、提出された回答だけを使う。

## Decisions

- Vendor grilling-viz from mathbullet/skills commit 5ab997fcb8a80da4938bacb0a86cbd568e1018a7 with its MIT notice, fetching the exact files during implementation as a public read. Keep renderer, scripts and design-system bytes unchanged.
- Adapt only SKILL.md and add agents/openai.yaml. Replace the dependency on the absent grilling skill with inline question-construction steps, and record every adaptation in references/upstream.md.
- Write questionnaires locally under .agent-artifacts/questionnaires/ and never commit answers.
- Route opinion requests through SPEC_USER_COMMUNICATION rather than AGENTS.md, so generated projects receive the rule through the managed specification on update.
- Require Node 18 or later for the renderer test and fail rather than skip when node is absent.
- Register every new managed file the way checked plan 107 registered a vendored skill: ownership.yaml copier_managed bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, SOURCE_REQUIRED and GENERATED_REQUIRED entries, root skill parity in check-root-agent-policy.py, generated bridge assertions, smoke coverage and the versioned copier-update source inventory.

## Tasks

- [ ] Fetch the pinned upstream files and LICENSE, compare them with the local copy, and record digests and adaptations in references/upstream.md.
- [ ] Add the root and managed skill copies, UI metadata and the generated bridge.
- [ ] Add the opinion-routing statements to both SPEC_USER_COMMUNICATION files and their markers to check-root-agent-policy.py.
- [ ] Add GrillingVizTest and its question fixture, and register it in tests/test-validation-tools.py.
- [ ] Register every new file and bridge.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite, and assert preserved project-owned bytes and existing validation.
- [ ] Obtain independent review of the exact in-scope patch, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle without pushing.

## Validation Notes

- Pre-activation review at d61b41e split the original plan 368 into this plan and the three plans named in docs/plan/backlog/README.md, because its four features share no invariant, its write scope missed the registration files every comparable checked plan touched, and its node --test witnesses are not admitted validation commands.
