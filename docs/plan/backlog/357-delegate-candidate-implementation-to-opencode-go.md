# Let OpenCode Go produce bounded implementation candidates

status: backlog
primary_invariant: An explicitly selected Go worker produces only an in-scope candidate under the existing attempt, receipt, correction and parent-validation gates, without receiving upstream credentials or lifecycle authority.
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
  - {"evidence":"run-sandboxed-plan-worker.py execute_isolated_attempt and correct_worker already accept --worker-binary; the custom route receives a verified contract, exact writable shadows and a completion-claims path, and supports one fresh correction.","kind":"existing_mechanism"}
  - {"evidence":"validate_worker_completion_claims, parent-derived worker receipts, Git patch admission and parent-owned validation are already shared across default and custom workers. Extend their attempt provenance without substituting worker claims for parent facts.","kind":"existing_mechanism"}
  - {"evidence":"The preceding transport and read-only plans implement the same credential-free OpenCode child launch used here. Existing custom attempt model/reasoning metadata is null, so explicit Go dispatch provenance belongs in the enumerated runner verification scope.","kind":"existing_mechanism"}
completion_conditions:
  - Explicit Go selection produces an admissible candidate from the exact source HEAD with edits restricted to the existing exact write_scope mounts and missing-file root.
  - Every initial and correction attempt binds the selected Go backend/model and verified process/claims evidence to its exact attempt; forged, missing, stale or inconsistent output fails before candidate admission.
  - The existing parent-only review, focused and authoritative validation, correction limit, stopped-ledger refusal and checked publication remain enforced for Go attempts.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - Root and generated installations expose the optional Go candidate route while legacy Codex and unrelated custom-worker behavior remain compatible.
completion_witness_map:
  - {"condition_sha256":"sha256:9d4031caec69eb17c8dbf422fe9cd43b92e06181a6053b3fade9cdc5fdc53a45","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:22b0df69b5b3b340a5954f8baf614266ef29a3ff00c915943686279b2bc0ff72","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:35bbbaf8e6054114bd753fca696793aacc7e563109f0a4fc68f047717a5935bd","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:5bc1e2bdec65fe1568c4fcfa0c2f0291d759e1ab49c1408ac4766ae1d3b3e057","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/opencode-plan-worker.py
  - template/.project-agent-workflow/scripts/opencode-plan-worker.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/project_workflow/opencode_go_execution.py
  - template/.project-agent-workflow/scripts/opencode_go_execution.py
  - docs/agent/opencode-go.json
  - template/docs/agent/opencode-go.json.jinja
  - .codex/skills/opencode-delegate/SKILL.md
  - .codex/skills/opencode-delegate/references/worker-contract.md
  - template/.project-agent-workflow/skills/opencode-delegate/SKILL.md
  - template/.project-agent-workflow/skills/opencode-delegate/references/worker-contract.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - AGENTS.md
  - template/AGENTS.md.jinja
  - references/orchestration.md
  - tests/opencode_go_candidates.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/smoke.sh
  - template/.project-agent-workflow/AGENTS.md.jinja
  - .codex/skills/opencode-delegate/agents/openai.yaml
  - template/.project-agent-workflow/skills/opencode-delegate/agents/openai.yaml
  - .agents/skills/opencode-delegate/SKILL.md
  - template/.agents/skills/opencode-delegate/SKILL.md
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/copier-update.sh
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/plan-execution-state.py
  - docs/plan/active/355-isolate-opencode-go-inference-credentials.md
  - docs/plan/backlog/356-delegate-read-only-tasks-to-opencode-go.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/copier-update.sh --require-copier
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The Go adapter consumes the runner contract and correction brief, reads required specifications directly, writes only bounded advisory claims, and returns an in-scope candidate without committing or changing lifecycle state.
  - A verified initial attempt and one fresh correction preserve source baseline and prior-patch lineage; unknown completion claims, error events, model drift, replay and out-of-scope writes never become accepted candidates.
  - The Go process and any repository code it runs cannot receive the real API key or escape the existing filesystem/network boundary; parent-owned validation remains credential-free and network-isolated.
  - Explicit Go routing remains subject to risk/ambiguity eligibility, attempt and review budgets, stopped-ledger gates and unchanged acceptance witnesses; no custom-worker error triggers the Codex fallback or replenishes an execution budget.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - The root/generated artifact inventory and mechanically rewritten counterparts for this plan stay aligned under the existing template checker.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d930bc55fa2da26dfb2e6a2bd4f2a0b00d7079bf28176e0828141c143967b5bd","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:72b4b9ee612345af0ad93689efed29eda6b85063c25fc7f41dd82388205ada6b","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:68efe554460079f7e5645eb24e5697d41905580d3d4cfc7a1a2a7b71bf15673c","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:8ded8e74d9aa6291e5f488ffb4529ab04a1e0e49f624c89b0af5fcac8721d6a0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - docs/plan/active/355-isolate-opencode-go-inference-credentials.md
  - docs/plan/backlog/356-delegate-read-only-tasks-to-opencode-go.md
checked_summary_ja: 既存の隔離実行を通じて OpenCode Go に実装候補と修正候補を生成させる。

## Decisions

- Keep the current parent orchestrator and its final interpretation, authorization, independent-review selection, validation acceptance, lifecycle, commit and publication ownership. The owner requested plan creation following the proposed staged CLI delegation approach; this authoring task does not execute these implementation plans.
- Implement this plan parent-direct in its task-bound worktree because its exact scope includes security or validation authority. Before product edits, prepare the parent-owned execution ledger in parent_direct mode with the required reviewer registry, continuation registry and adversarial preflight. Keep existing review budgets and stop transitions; do not delegate these authority edits to the new Go worker.
- Use Tier 2 for the new external execution boundary. Keep root and generated counterparts aligned in each plan. Default installations stay disabled, and the Codex routing, Sol independent review and existing legacy candidate behavior remain unchanged unless a caller explicitly selects the admitted Go route.
- Support the observed OpenCode 1.18.30 Chat Completions path first. Require an explicit exact model ID and an admitted protocol in local configuration; do not infer entitlement from the catalog, a requested model from a runtime event, or model quality from transport success. Reject unsupported protocols before dispatch; adding Messages or Responses is outside these plans.
- Do not install, upgrade or authenticate a CLI automatically. Automated acceptance uses credential-free local fixtures and does not require a subscription, contact OpenCode Go or consume paid usage. A live check is separately task-authorized and never substitutes for deterministic acceptance.
- The existing orchestrator invokes OpenCode through the existing candidate and correction runner while retaining parent-only patch admission and validation.
- Require an explicit implementation selection in project-owned Go configuration plus explicit parent dispatch. Keep default configuration disabled/read_only until the owner enables candidate use. Reuse --worker-binary as the custom execution seam rather than adding provider model names to Codex profiles.
- Start the parent credential relay before the isolated attempt and pass only its mounted socket and nonsecret configuration to the Go adapter. Integrate private-network/socket wiring only for the selected Go path. Preserve the legacy custom command environment and manifest compatibility; never grant an arbitrary custom executable the Go credential route.
- The adapter receives no default stdin prompt or Codex auth. Build its instruction from SANDBOXED_PLAN_WORKER_WORKER_CONTRACT and the named plan/spec files; honor WORKER_REPO, SCRATCH_DIR, NEW_FILE_ROOT, COMPLETION_CLAIMS and CORRECTION_BRIEF. It supplies only the exact allowed worker claims. The parent still derives Git facts and the final receipt.
- Retain the existing receipt schema. Add bounded parent-authored Go dispatch provenance at the attempt/manifest boundary and update every initial/correction verification path in the runner. Bind requested settings to the exact attempt and distinguish runtime-observed values from unobserved provider execution. Legacy custom null model metadata stays valid legacy evidence.
- Permit Go writable execution only for already eligible low/ordinary risk and ambiguity inputs; either high still refuses delegation. Keep Sol reserved for independent review. Stop on authentication, network, 429, protocol, semantic or validation failures; no automatic provider/model fallback for the Go custom route.
- Require fresh scratch, OpenCode session, socket and bridge for the single permitted correction; preserve the exact source HEAD, prior manifest and patch digests and parent correction brief. A failed worker does not authorize another attempt, review, validation, apply or lifecycle transition.
- Update both the generated root AGENTS seed and the managed .project-agent-workflow/AGENTS.md body so preserved downstream root instructions can discover the updated delegation route.
- Keep this plan in backlog until every integration gate has one checked archive. Resolve the same plan IDs through docs/plan/checked.md and update the gate/context references through the governed lifecycle before promotion. Do not start merely because its identifier is larger; execute this chain serially.

## Tasks

- [ ] Before edits, verify exact write scope and current required specifications, prepare parent-direct execution evidence, and record the unchanged Codex baseline. Do not start a sandboxed candidate worker to edit runner, policy or validation-authority files.
- [ ] Implement the Go adapter and connect it to initial/correction custom execution with parent-started relay, private-network mounts and explicit model selection. Keep configuration and instructions isolated as in the checked read-only predecessor while allowing only existing exact writable shadows.
- [ ] Bind Go dispatch provenance to parent-known attempt identity and validate it on run, correction, candidate read, preflight, validation and apply paths; reject missing, swapped or inconsistent evidence while retaining legacy manifests.
- [ ] Extend fixture cases to cover a successful candidate, a failed attempt with partial changes, a new allowed file, denied authority edits, exact claims, replay, one correction and refused second correction, stopped ledgers, Go 429/no fallback, model drift, process interruption, credential isolation during repository code execution and parent-owned validation.
- [ ] Update the orchestrator and delegation instructions and local configuration route to select the adapter explicitly. Keep formal review on the existing independent reviewer route, not on a Go helper claiming review authority.
- [ ] Register candidate tests in the admitted test entrypoint, enforce all mirrored paths and run generated-layout smoke cases for the Go route and unchanged Codex/custom defaults. Re-run the checked read-only helper cases as integration coverage; do not create a verification-only successor.
- [ ] Refresh the delegation skill UI metadata and root/generated discovery bridges when adding candidate dispatch; keep the advertised capability conditional on explicit local enablement and the checked implementation route.
- [ ] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and the corresponding tests/copier-update.sh fixtures so their versioned source contains every managed file introduced here. Assert their exact generated locations after copy/update and preservation of existing project-owned policy/configuration; do not weaken the fixture grammar or existing checks.
- [ ] Obtain independent review against the exact changed files and the security cases, resolve findings within the existing budget, then run focused validation and the unchanged authoritative suites. Publish the accepted task commit through manage-plan-worktrees.py; do not push.

## Validation Notes

- Pre-admission local evidence: OpenCode 1.18.30 with a temporary empty HOME/config, denied tools and a synthetic loopback provider exited 0; two streamed POST /v1/chat/completions requests selected glm-5.3 and emitted step_start, text and step_finish events. No Go API or real credential was used.
- Requested settings, runtime reports and provider execution are distinct evidence classes. Live entitlement and answer quality remain unverified; deterministic fixture success establishes only the stated implementation conditions.
- Implementation has not started. Focused and authoritative commands in this manifest are required future witnesses, not results of this plan-authoring task.
