# Generate project diagrams and Web demos and install search and opinion skills

status: backlog
primary_invariant: Project automation produces only evidence-bound configured artifacts inside current task authority, preserves previous successful outputs on failure and does not expand external access or overwrite project-owned settings.
task_types:
  - template_workflow
  - validation_tools
  - security
  - skill_authoring
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Both complete-plan.sh entrypoints expose a parent-owned boundary before the ready transition; .agents skill bridges route to managed bodies and ownership.yaml preserves docs/agent/** on update.","kind":"existing_mechanism"}
  - {"evidence":"The installed grilling-viz renderer generated a standalone three-question HTML; Node checks passed for schema, inline scripts, initially empty answers, serialization, restoration and copied text.","kind":"bounded_prototype"}
  - {"evidence":"Remotion 4.0.524 exports bundle and renderMedia. Agent Reach 1.5.0 delegates search to mcporter/Exa. Pinned upstream revisions and the grilling-viz MIT license were inspected before admission.","kind":"existing_mechanism"}
completion_conditions:
  - Changed specifications or data structures produce evidence-bound conceptual Mermaid diagrams and ER diagrams where a relational model applies; stale evidence and unsafe paths refuse without overwriting prior output.
  - After initial scenario setup, changed Web UI inputs trigger real browser recording and Remotion rendering; unchanged inputs reuse verified output and failed recording or rendering preserves prior output.
  - Generated projects discover Agent Reach research guidance that uses supported upstream clients through existing per-provider authorization and reports unavailable routes without fabricating results.
  - Agents seeking user opinions generate standalone grilling-viz questionnaires with choices and free text, retain answers across safe updates and use submitted answers rather than assuming consent.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:9ab18d3632eaa400788b035f86dde7d3d2b12f8f0270cf1e31758914c702dd71","witness":"python3 tests/test-project-artifacts.py"}
  - {"condition_sha256":"sha256:3ae541828832349cc864f183d72efe868c65618a3ffd1b63faec2143d0900dba","witness":"node --test tests/test-web-demo.mjs"}
  - {"condition_sha256":"sha256:a2ef3e4817cb5f594f303f38d36b946ced2609b1192f997fbe5bb32185e4820f","witness":"python3 tests/test-project-artifacts.py"}
  - {"condition_sha256":"sha256:a2f14e060b3c4ae46698f84a94f3f684a2b746f1ab757c6830c60e7715048548","witness":"node --test tests/test-grilling-viz.mjs"}
  - {"condition_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","witness":"python3 tests/test-project-artifacts.py"}
write_scope:
  - scripts/project-artifacts.py
  - template/.project-agent-workflow/scripts/project-artifacts.py
  - .codex/skills/project-artifacts/SKILL.md
  - template/.project-agent-workflow/skills/project-artifacts/SKILL.md
  - .codex/skills/project-artifacts/agents/openai.yaml
  - template/.project-agent-workflow/skills/project-artifacts/agents/openai.yaml
  - .codex/skills/project-artifacts/references/configuration.md
  - template/.project-agent-workflow/skills/project-artifacts/references/configuration.md
  - .codex/skills/project-artifacts/references/web-demo.md
  - template/.project-agent-workflow/skills/project-artifacts/references/web-demo.md
  - template/.agents/skills/project-artifacts/SKILL.md
  - scripts/record-web-demo.mjs
  - template/.project-agent-workflow/scripts/record-web-demo.mjs
  - scripts/web-demo-composition.jsx
  - template/.project-agent-workflow/scripts/web-demo-composition.jsx
  - tests/test-web-demo.mjs
  - .codex/skills/agent-reach/SKILL.md
  - template/.project-agent-workflow/skills/agent-reach/SKILL.md
  - .codex/skills/agent-reach/agents/openai.yaml
  - template/.project-agent-workflow/skills/agent-reach/agents/openai.yaml
  - .codex/skills/agent-reach/references/upstream.md
  - template/.project-agent-workflow/skills/agent-reach/references/upstream.md
  - template/.agents/skills/agent-reach/SKILL.md
  - tests/test-grilling-viz.mjs
  - .codex/skills/grilling-viz/SKILL.md
  - template/.project-agent-workflow/skills/grilling-viz/SKILL.md
  - .codex/skills/grilling-viz/agents/openai.yaml
  - template/.project-agent-workflow/skills/grilling-viz/agents/openai.yaml
  - .codex/skills/grilling-viz/references/upstream.md
  - template/.project-agent-workflow/skills/grilling-viz/references/upstream.md
  - .codex/skills/grilling-viz/scripts/render.mjs
  - template/.project-agent-workflow/skills/grilling-viz/scripts/render.mjs
  - .codex/skills/grilling-viz/scripts/answer.js
  - template/.project-agent-workflow/skills/grilling-viz/scripts/answer.js
  - .codex/skills/grilling-viz/scripts/components.js
  - template/.project-agent-workflow/skills/grilling-viz/scripts/components.js
  - .codex/skills/grilling-viz/design-system/tokens.css
  - template/.project-agent-workflow/skills/grilling-viz/design-system/tokens.css
  - .codex/skills/grilling-viz/design-system/components.css
  - template/.project-agent-workflow/skills/grilling-viz/design-system/components.css
  - .codex/skills/grilling-viz/design-system/component-samples.html
  - template/.project-agent-workflow/skills/grilling-viz/design-system/component-samples.html
  - .codex/skills/grilling-viz/LICENSE
  - template/.project-agent-workflow/skills/grilling-viz/LICENSE
  - template/.agents/skills/grilling-viz/SKILL.md
  - docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - template/.project-agent-workflow/docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/test-project-artifacts.py
  - template/.project-agent-workflow/ownership.yaml
  - README.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - references/orchestration.md
  - copier.yml
  - docs/agent/external-services.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-project-artifacts.py
  - node --test tests/test-web-demo.mjs
  - node --test tests/test-grilling-viz.mjs
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Changed specifications or data structures produce evidence-bound conceptual Mermaid diagrams and ER diagrams where a relational model applies; stale evidence and unsafe paths refuse without overwriting prior output.
  - After initial scenario setup, changed Web UI inputs trigger real browser recording and Remotion rendering; unchanged inputs reuse verified output and failed recording or rendering preserves prior output.
  - Generated projects discover Agent Reach research guidance that uses supported upstream clients through existing per-provider authorization and reports unavailable routes without fabricating results.
  - Agents seeking user opinions generate standalone grilling-viz questionnaires with choices and free text, retain answers across safe updates and use submitted answers rather than assuming consent.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:9ab18d3632eaa400788b035f86dde7d3d2b12f8f0270cf1e31758914c702dd71","stage":"focused","witness":"python3 tests/test-project-artifacts.py"}
  - {"acceptance_sha256":"sha256:3ae541828832349cc864f183d72efe868c65618a3ffd1b63faec2143d0900dba","stage":"focused","witness":"node --test tests/test-web-demo.mjs"}
  - {"acceptance_sha256":"sha256:a2ef3e4817cb5f594f303f38d36b946ced2609b1192f997fbe5bb32185e4820f","stage":"focused","witness":"python3 tests/test-project-artifacts.py"}
  - {"acceptance_sha256":"sha256:a2f14e060b3c4ae46698f84a94f3f684a2b746f1ab757c6830c60e7715048548","stage":"focused","witness":"node --test tests/test-grilling-viz.mjs"}
  - {"acceptance_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","stage":"focused","witness":"python3 tests/test-project-artifacts.py"}
checked_summary_ja: 仕様と画面の変更に図と操作動画を追従させ、検索と意見収集のスキルを導入する。

## Decisions

- Use the owner-selected specification/data-model and Web UI change triggers at task completion. Retain desktop and mobile recording as later work.
- Implement parent-direct because completion lifecycle, validation registration and external-access integration require parent-owned authority. Initialize an external execution ledger and obtain independent review before focused and authoritative validation.
- Use project-owned explicit source lists and evidence-bound graph data; agents refresh concepts from specifications rather than guessing arbitrary ORM schemas.
- Record configured local Web test scenarios and render captions with Remotion. Dependencies stay in the project environment; hooks do not install tools, configure accounts or start production services.
- Keep Stop hooks read-only. Generate before ordinary validation and recheck at completion; configured failures stop completion without replacing successful outputs.
- Keep graph text reviewable in Git and videos and questionnaires local under .agent-artifacts. Preserve project settings on update.
- Vendor grilling-viz from mathbullet/skills commit 5ab997fcb8a80da4938bacb0a86cbd568e1018a7 with MIT notice. Author Agent Reach guidance against da5044d26fc6adddb6554d5679c94ac22e76e428; use Remotion API evidence from 91bba18557b69b9c9595dfb805e27b043b4db26d.

## Tasks

- [ ] Implement graph/config validation, content-based freshness and atomic updates with adversarial fixtures.
- [ ] Implement Web scenario recording, local Remotion composition and bounded failures; run a local interactive fixture with installed dependencies.
- [ ] Add project-artifacts, Agent Reach and grilling-viz skills with source provenance and mirrored managed copies.
- [ ] Wire task completion and opinion routing and register focused tests and copy/update preservation coverage.
- [ ] Review the exact in-scope patch independently, run focused checks and unchanged authoritative suites, finalize and publish the accepted commit without pushing.

## Validation Notes

- Owner selected A for specification changes, A for Web UI task completion after scenario setup and A for Web-first recording on 2026-09-15.
- New external publication, account configuration and automatic dependency installation remain outside generated automation.
- Plan 360 currently occupies the single runnable-plan slot and has a live task worktree. This plan is queued without changing that task; promotion must wait until the slot is available.
