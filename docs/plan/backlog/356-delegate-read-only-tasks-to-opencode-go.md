# Let the orchestrator delegate read-only tasks to OpenCode Go

status: backlog
primary_invariant: A parent-selected OpenCode Go helper reads only the admitted repository inputs and returns a bounded advisory answer without acquiring repository write or lifecycle authority.
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The existing Bubblewrap builder enforces read-only source mounts, clearenv and private namespaces; the checked transport predecessor provides the narrowly scoped inference connection. Skills and generated .agents discovery bridges are already shipped by this repository.","kind":"existing_mechanism"}
  - {"evidence":"The local OpenCode 1.18.30 fixture emitted step_start/text/step_finish JSON events for opencode-go/glm-5.3; run --pure --model --format json is supported. This proves local protocol plumbing only, not account authentication or answer quality.","kind":"bounded_prototype"}
  - {"evidence":"copier.yml already preserves docs/agent/** and seeds project-owned configuration from optional answers. check-copier-template.py and tests/smoke.sh enforce installation alignment and update preservation.","kind":"existing_mechanism"}
completion_conditions:
  - An explicitly configured parent dispatch starts one fresh OpenCode helper against an admitted read-only snapshot through the checked credential-isolating transport and returns its advisory answer.
  - Unlisted files, source writes, commands, descendant agents, external tools and host/project configuration injection cannot be used by the read-only helper.
  - Success requires a bounded complete event stream with a matching request/session identity and an answer; nonzero exits, error events, empty/truncated output, unexpected model selection and exhausted limits fail without automatic fallback.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - Root and generated projects discover the delegation skill and preserve a project-owned disabled-by-default configuration on Copier update.
completion_witness_map:
  - {"condition_sha256":"sha256:b521ae54aa3038e2049ea99cdaf805405437e86daa090b8f812658df2bc62545","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:8b72e1861efe3c197547654379dd2646ec43db5bbcaf5ab010b4f099249f9f93","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:8bc4995005ed8ec5dc46d0faa9ccc4c6f768bc4a2d34b288b314388c8a5e82d9","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:304711a599b71f30d117e411aee75a245631454dcdc146b9aa99a67e6eae1a1e","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-opencode-helper.py
  - template/.project-agent-workflow/scripts/run-opencode-helper.py
  - scripts/project_workflow/opencode_go_execution.py
  - template/.project-agent-workflow/scripts/opencode_go_execution.py
  - docs/agent/opencode-go.json
  - template/docs/agent/opencode-go.json.jinja
  - copier.yml
  - .codex/skills/opencode-delegate/SKILL.md
  - .codex/skills/opencode-delegate/agents/openai.yaml
  - .codex/skills/opencode-delegate/references/worker-contract.md
  - .agents/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/opencode-delegate/references/worker-contract.md
  - template/.agents/skills/opencode-delegate/SKILL.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - tests/opencode_go_helpers.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - tests/smoke.sh
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/ownership.yaml
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/run-sandboxed-plan-worker.py
  - docs/plan/replanned/2026/09/01-15/355-isolate-opencode-go-inference-credentials.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/copier-update.sh --require-copier
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The orchestrator can invoke the shipped helper command with an exact Go model, bounded task and explicit repository input paths and receive an answer while retaining every adoption and validation decision.
  - A real isolated fixture proves source/ref/index bytes stay unchanged and the helper cannot obtain host credentials, run repository code, expand input paths through symlinks, load external plugins/MCP/skills or use a different provider.
  - The result records the requested backend/model and directly observed runtime identity separately, never upgrades a request to provider-execution evidence, and reports bounded failures including 429, timeout, error events and incomplete output.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - The root/generated artifact inventory and mechanically rewritten counterparts for this plan stay aligned under the existing template checker.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6a93344caf98fde95f6920a3db153727b5203c0bc6f8700503494d5c2c64b59c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:2c6b904e8013fa92f54ad13d9707d3d2ad62ba0d96eca963e72e395529132af0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:518cd64e6d0416977a47728c0c8c65705c78b4d993a7b86279942f16329a2426","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - docs/plan/active/355-isolate-opencode-go-inference-credentials.md
checked_summary_ja: 親のオーケストレーターから OpenCode Go に読み取り専用の調査を委任する。

## Decisions

- Keep the current parent orchestrator and its final interpretation, authorization, independent-review selection, validation acceptance, lifecycle, commit and publication ownership. The owner requested plan creation following the proposed staged CLI delegation approach; this authoring task does not execute these implementation plans.
- Implement this plan parent-direct in its task-bound worktree because its exact scope includes security or validation authority. Before product edits, prepare the parent-owned execution ledger in parent_direct mode with the required reviewer registry, continuation registry and adversarial preflight. Keep existing review budgets and stop transitions; do not delegate these authority edits to the new Go worker.
- Use Tier 2 for the new external execution boundary. Keep root and generated counterparts aligned in each plan. Default installations stay disabled, and the Codex routing, Sol independent review and existing legacy candidate behavior remain unchanged unless a caller explicitly selects the admitted Go route.
- Support the observed OpenCode 1.18.30 Chat Completions path first. Require an explicit exact model ID and an admitted protocol in local configuration; do not infer entitlement from the catalog, a requested model from a runtime event, or model quality from transport success. Reject unsupported protocols before dispatch; adding Messages or Responses is outside these plans.
- Do not install, upgrade or authenticate a CLI automatically. Automated acceptance uses credential-free local fixtures and does not require a subscription, contact OpenCode Go or consume paid usage. A live check is separately task-authorized and never substitutes for deterministic acceptance.
- The existing orchestrator invokes an isolated OpenCode process to read only the selected repository snapshot and returns an advisory answer.
- Expose run-opencode-helper.py as the parent callable entrypoint and use the shared credential-free child launcher in opencode_go_execution.py. Do not replace the parent model, Codex agent TOML profiles, built-in spawn_agent interface or Sol independent-review role.
- Seed docs/agent/opencode-go.json with schema_version 1, mode disabled, an explicit model selection map, supported protocol and bounded execution settings; store no credential. Add an optional Copier mode with disabled as its default. Use the existing docs/agent preservation rule so updates do not overwrite project-owned choices.
- For mode read_only, construct a minimal snapshot containing only parent-approved repository-relative regular files and required policy inputs; reject unsafe paths and secret/private configuration inputs before provider dispatch. Mount it read-only and make host checkout/Git/config paths inaccessible. Only task scratch is writable.
- Start each invocation with a new HOME/XDG config/data/cache boundary, networking disabled except the mounted transport socket, and parent-generated provider configuration. Disable ambient project/global configuration, external/default plugins, external skills, MCP, autoupdate, share, agent recursion and command execution. Use an exact read-path permission allowlist, not prompt-only restrictions or --pure alone.
- Pin both primary and auxiliary model requests to the exact selected supported model and a fixed title; any provider/model drift is an error. Do not assume every CLI version has the same isolation switches: reject a runtime that cannot enforce the declared boundaries.
- Parse JSON events as events, not one JSON answer. Retain only bounded task/session identity, requested/observed settings, answer and status; keep large evidence local with missing transcript/hook coverage explicit. The model may analyze source text but may not execute it.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the updated delegation route.
- Keep this plan in backlog until every integration gate has one checked archive. Resolve the same plan IDs through docs/plan/checked.md and update the gate/context references through the governed lifecycle before promotion. Do not start merely because its identifier is larger; execute this chain serially.

## Tasks

- [ ] Before edits, verify exact write scope and current required specifications, prepare parent-direct execution evidence, and record the unchanged Codex baseline. Do not start a sandboxed candidate worker to edit runner, policy or validation-authority files.
- [ ] Implement helper input validation, snapshot creation, isolated execution and structured output using the already checked transport. Include fixture tests invoking the real installed CLI against a local fake provider when available; deterministic fake-CLI cases remain mandatory on every host.
- [ ] Test command/descendant-agent attempts, read and symlink escapes, malicious repository config/plugins, ambient credentials, unexpected models, malformed/oversized JSON, missing final answer, failure events at process exit 0, nonzero exits, cancellation and retry refusal. Register the new tests in the existing admitted test entrypoint.
- [ ] Add the concise opencode-delegate skill, direct worker-contract reference and UI metadata; root and generated discovery bridges must route to their correct managed body. Tell the parent when to choose Go, which entrypoint to call, what to pass, how to await results and how to reject unsupported or failed dispatch.
- [ ] Add opt-in configuration and Copier seeding, update root/generated instruction routing and enforce installation/parity. Extend smoke fixtures to prove fresh-copy defaults and update preservation of a locally edited Go configuration without touching personal auth or executing a real model.
- [ ] Reserve the generated opencode-delegate discovery bridge in ownership.yaml and test fresh copy, retained project-owned configuration and managed bridge delivery during Copier update. Do not overwrite an existing project-owned bridge on an unclassified collision.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and the corresponding tests/copier-update.sh fixtures so their versioned source contains every managed file introduced here. Assert their exact generated locations after copy/update and preservation of existing project-owned policy/configuration; do not weaken the fixture grammar or existing checks.
- [ ] Obtain independent review against the exact changed files and the security cases, resolve findings within the existing budget, then run focused validation and the unchanged authoritative suites. Publish the accepted task commit through manage-plan-worktrees.py; do not push.

## Validation Notes

- Pre-admission local evidence: OpenCode 1.18.30 with a temporary empty HOME/config, denied tools and a synthetic loopback provider exited 0; two streamed POST /v1/chat/completions requests selected glm-5.3 and emitted step_start, text and step_finish events. No Go API or real credential was used.
- Requested settings, runtime reports and provider execution are distinct evidence classes. Live entitlement and answer quality remain unverified; deterministic fixture success establishes only the stated implementation conditions.
- Implementation has not started. Focused and authoritative commands in this manifest are required future witnesses, not results of this plan-authoring task.
