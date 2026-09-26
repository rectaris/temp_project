# Record configured Web UI scenarios and render captioned demos with Remotion

status: backlog
primary_invariant: A configured Web demo is re-recorded and re-rendered only when its declared inputs change, a failed recording or render leaves the prior verified output byte-identical, and no hook installs a dependency, configures an account or starts a production service.
task_types:
  - template_workflow
  - skill_authoring
  - security
  - browser_automation
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Outside the repository at 2026-09-26, Playwright 1.63.0 recorded a local page click to WebM with an existing chromium headless shell via executablePath, and Remotion 4.0.529 bundle, selectComposition and renderMedia rendered a 2.0 s captioned H.264 over that recording with browserExecutable and no license key.","kind":"bounded_prototype"}
  - {"evidence":"The plan that adds project-artifacts.py and the completion check provides content-digest freshness, atomic replacement and the conditional pre-ready hook; this plan adds a web_demos kind to the same configuration and command.","kind":"existing_mechanism"}
  - {"evidence":"tests/test-validation-tools.py already runs tests/validation_tools modules, so deterministic cases run there with an injected recorder and renderer; plan 368 admits python3 tests/test-web-demo-live.py in both allowlists for the live test, which fails closed when the browser dependencies are absent.","kind":"existing_mechanism"}
completion_conditions:
  - A configured web demo is recorded and rendered only when the digest of its scenario, declared source files and caption text changes; unchanged inputs reuse the verified output without starting a browser.
  - A failing, timed-out or dependency-missing recording or render stops with a bounded error, leaves the prior output and its digest record byte-identical, and never installs a dependency.
  - The live test records the committed fixture site in a real Playwright browser, renders it with real Remotion into a playable H.264 file under .agent-artifacts, and fails when Playwright, Remotion or a browser is unavailable.
  - The specification and skill state that a project declares Playwright and Remotion as its own dependencies, that Remotion requires a company license for organizations it does not exempt, and that the template sets no license key, and the root policy check asserts those statements.
  - Root and generated recorder, composition, skill reference and specification stay aligned, and every new managed file is registered and passes the template checker.
  - A real Copier update installs the demo files and preserves the project-owned artifact configuration, product dependency manifests and existing workflow behavior.
completion_witness_map:
  - {"condition_sha256":"sha256:995a0ce183e285b00d601cea39263cb69ea495d44257d5173f39ba88847b0c7a","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a3531b5a210ac811ff22903ff74aba51c4d7506ebdffec63f46d666e957510a1","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:173b1aed247dd2f29ab24313a46399024d998a703159a883ed6b90be4b2c7efb","witness":"python3 tests/test-web-demo-live.py"}
  - {"condition_sha256":"sha256:b3d698243c6c86c8c7457bcd90f702de9fd4a23f96aa9955ea9f6f0731ab60bb","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:deb63df8b89301e0cd6f89e1b5e74f30eb62b5be0c3bb3b3ef808b8a0e5e2a8b","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:b814d60f24b19a20f8656857ab5550e431d8f59fec846a1155e513cfcea180cf","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - scripts/project-artifacts.py
  - template/.project-agent-workflow/scripts/project-artifacts.py
  - scripts/record-web-demo.mjs
  - template/.project-agent-workflow/scripts/record-web-demo.mjs
  - scripts/web-demo-composition.jsx
  - template/.project-agent-workflow/scripts/web-demo-composition.jsx
  - .codex/skills/project-artifacts/references/web-demo.md
  - template/.project-agent-workflow/skills/project-artifacts/references/web-demo.md
  - .codex/skills/project-artifacts/SKILL.md
  - template/.project-agent-workflow/skills/project-artifacts/SKILL.md
  - docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - template/.project-agent-workflow/docs/agent/SPEC_PROJECT_ARTIFACTS.md
  - tests/validation_tools/web_demo.py
  - tests/test-web-demo-live.py
  - tests/fixtures/web-demo/site/index.html
  - tests/fixtures/web-demo/scenario.json
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
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - .codex/skills/browser-ops/SKILL.md
  - .codex/skills/browser-ops/references/browser-run-policy.md
  - references/orchestration.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 tests/test-web-demo-live.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - After initial scenario setup, changed Web UI inputs trigger real browser recording and Remotion rendering; unchanged inputs reuse verified output and failed recording or rendering preserves prior output.
  - Root and generated skills, ownership, routing and completion wiring remain aligned; Copier copy and update preserve project-owned configuration and existing workflow behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:3ae541828832349cc864f183d72efe868c65618a3ffd1b63faec2143d0900dba","stage":"focused","witness":"python3 tests/test-web-demo-live.py"}
  - {"acceptance_sha256":"sha256:96ea69c75ea5f16a959af889e6a4e161abb7b8982bf7f583d7c24839c53fc4e2","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - docs/plan/backlog/368-generate-evidence-bound-project-diagrams.md
checked_summary_ja: 設定したWeb画面の操作を実ブラウザーで録画し、Remotionで字幕付きの操作動画にする。

## Decisions

- Start only after plan 368 is checked, because this plan extends its configuration, command, completion check and skill.
- Keep Remotion as the owner selected on 2026-09-26. Document its license terms and that the template configures no license key; a project that needs a company license obtains it itself.
- Record configured local scenarios with Playwright and render captions with Remotion. Both are project-owned dependencies; the template never edits a product package.json or lockfile, and hooks never install tools, configure accounts or start production services.
- Record Web-first only. Desktop and mobile recording stay later work.
- Keep videos under .agent-artifacts/web-demos/ and never commit them; keep only the digest record beside the configuration.
- Prove freshness, reuse and preservation deterministically with injected fake recorder and renderer commands; prove real recording and rendering with tests/test-web-demo-live.py, a parent-run focused witness that fails closed without dependencies and is not part of CI.
- Use the allowlist entry for tests/test-web-demo-live.py that plan 368 admits; this plan does not edit the allowlists.
- Register every new managed file the way checked plan 107 registered a vendored skill: ownership.yaml copier_managed bridge entries with the matching CURRENT_OWNERSHIP_SHA256 in both validate-copier-update.py copies, SOURCE_REQUIRED and GENERATED_REQUIRED entries, root skill parity in check-root-agent-policy.py, generated bridge assertions, smoke coverage and the versioned copier-update source inventory.

## Tasks

- [ ] Add the web_demos configuration kind, scenario schema and digest record to project-artifacts.py and the specification.
- [ ] Implement record-web-demo.mjs and web-demo-composition.jsx with bounded timeouts and clear missing-dependency errors.
- [ ] Add WebDemoTest with fake recorder and renderer commands and register it in tests/test-validation-tools.py.
- [ ] Add the committed fixture site and scenario and tests/test-web-demo-live.py, and run it locally against dependencies installed outside the repository.
- [ ] Add the web-demo skill reference with the license, dependency and no-install statements and their policy markers.
- [ ] Register every new file.
- [ ] Extend the update-source inventory and real update scenarios, reading the whole v1.4.5 migration guardian rule in references/orchestration.md before running the update suite, and assert preserved project-owned bytes and existing validation.
- [ ] Obtain independent review of the exact in-scope patch, run the focused checks, then the full validation suite once, and publish through the ordinary lifecycle without pushing.

## Validation Notes

- Pre-activation review at d61b41e split the original plan 368 into this plan and the three plans named in docs/plan/backlog/README.md, because its four features share no invariant, its write scope missed the registration files every comparable checked plan touched, and its node --test witnesses are not admitted validation commands.
- The live witness python3 tests/test-web-demo-live.py is not yet an admitted validation command; plan 368 admits it, so this plan passes the validation-command check only after its integration gate is met.
