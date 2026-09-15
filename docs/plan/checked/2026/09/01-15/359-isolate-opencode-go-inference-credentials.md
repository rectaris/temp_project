# Keep OpenCode Go credentials outside delegated execution

status: checked
implementation_mode: parent_direct
primary_invariant: A delegated process can consume only the parent-authorized bounded inference route and cannot read or persist the upstream Go credential.
replan_sources:
  - docs/plan/active/358-isolate-opencode-go-inference-credentials.md
replan_contract: docs/plan/replanned/contracts/358-isolate-opencode-go-inference-credentials.json
integration_gates:
  - This plan proves every acceptance item of plan 358 together, because the credential boundary, the bounded failure behavior and the Copier registration are one transport change and cannot be witnessed separately.
successor_plans:
  - docs/plan/active/359-isolate-opencode-go-inference-credentials.md
inherited_acceptance_digests:
  - sha256:f93cbe951a4c4f237d6d4e522e5e47c08c6fbcdb8edb717277aff35d44ea4963
  - sha256:5e8b5647ad3966ed9bb4a2e4e78a3314e30eb2455502834e63656afaa9577722
  - sha256:94b888ec470ce67d2d89b3a400cefb0ff112038bf186e75f31bc80707260fec7
  - sha256:915259801ea25997dc22d84ddcdc0c5663e6ea97a82d87471e25a9553720e5d3
  - sha256:8f9bd49f356ee91e4a31c3731a85d881cb1b63c98aeb573ee0f74df0d518aeed
  - sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb
  - sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f
integration_source_ids:
  - 358
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
  - {"evidence":"run-sandboxed-plan-worker.py build_bwrap_command already supports private PID/network namespaces, clearenv, read-only inputs and writable scratch. Python standard-library Unix sockets and HTTP serving provide the bounded relay and bridge primitives.","kind":"existing_mechanism"}
  - {"evidence":"OpenCode 1.18.30 accepted provider.opencode-go.options.baseURL/apiKey pointing to a credential-free local server; glm-5.3 requests used /v1/chat/completions with streaming and produced JSON text and step_finish events at exit 0.","kind":"bounded_prototype"}
  - {"evidence":"check-external-service-policy.py and the versioned external-service specification already separate runtime configuration, task authorization, exact target and denied effects. The relay retains that gate before each upstream request.","kind":"existing_mechanism"}
  - {"evidence":"A real Bubblewrap --unshare-all child with an owner-only Unix socket mounted read-only connected to the parent fixture and returned LOCAL_SOCKET_OK at exit 0. No upstream connection or real credential was used; end-to-end HTTP bridging remains an implementation test.","kind":"bounded_prototype"}
completion_conditions:
  - A parent-owned Unix-socket relay forwards only the fixed Go Chat Completions endpoint and exact admitted model after task-scoped provider authorization; malformed or unapproved requests never reach upstream.
  - An isolated child with a private network namespace can use the local bridge but cannot read the upstream credential from its files, environment or proc view, nor reach an arbitrary upstream destination.
  - Request count, elapsed time and byte limits end the relay, bridge and process group; malformed streams, upstream errors and interruption yield a bounded failure without a retry or secret-bearing diagnostic.
  - The transport exposes one context-managed start/close API that yields a nonsecret socket endpoint, accepts per-request authorization and returns sanitized terminal status, usable by both later launchers without editing this module.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - Both root and generated layouts install the same transport behavior and its external-service boundary documentation.
completion_witness_map:
  - {"condition_sha256":"sha256:3fded941adaaa412f8ee1ef840f958113740f51fc0c0bf4c8d50c18ff266f6d2","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:5f760985aff55baf516277e0313f71fccbe42e5db8e32c5dc1da48d4e1492fe8","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:fc7f9a53b4761c06ad3b0bf5275d69197eb159481d2561b3b825697eb4614a27","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:739bb86e9a41655482744ceb45979cabc46c47c4d2df06a165904f66f9281e18","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:fe7a5cbf6380d7492e0e35d08734346191261fd41c04982df3b1617d237d2b85","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/project_workflow/opencode_go_transport.py
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/scripts/opencode_go_transport.py
  - tests/opencode_go_transport.py
  - tests/test-sandboxed-plan-worker.py
  - scripts/check-copier-template.py
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - docs/agent/external-services.yaml
  - template/docs/agent/external-services.yaml.jinja
  - tests/validation_tools/external.py
  - scripts/check-root-agent-policy.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - scripts/run-sandboxed-plan-worker.py
  - scripts/check-external-service-policy.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - tests/copier-update.sh --require-copier
  - python3 scripts/check-copier-template.py
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The relay fixes upstream host/path/model, strips downstream authentication, refuses redirects and CONNECT, authorizes each actual upstream request, and handles a bounded streamed response without exposing its key.
  - Credential sentinel fixtures remain absent from child-readable files/environment/proc, subprocess arguments, error records and retained outputs; denied destinations and unauthorized model changes make zero upstream requests.
  - Success, HTTP errors, malformed and truncated streams, oversized bodies, request-budget exhaustion, timeout and cancellation terminate predictably and leave no bridge or relay process running.
  - Root and generated policies name the Go provider without enabling it implicitly; v1 disabled/unconfigured and v2 missing configuration/task authorization or denied effects refuse every upstream call.
  - The callable transport API fixes socket ownership, selected model, authorization callback, budgets, sanitized terminal result and idempotent close; child exit and parent cancellation close all resources.
  - Versioned Copier update sources include the new managed files and copy/update fixtures install them without replacing existing project-owned policy or configuration bytes.
  - The root/generated artifact inventory and mechanically rewritten counterparts for this plan stay aligned under the existing template checker.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:f93cbe951a4c4f237d6d4e522e5e47c08c6fbcdb8edb717277aff35d44ea4963","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:5e8b5647ad3966ed9bb4a2e4e78a3314e30eb2455502834e63656afaa9577722","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:94b888ec470ce67d2d89b3a400cefb0ff112038bf186e75f31bc80707260fec7","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:915259801ea25997dc22d84ddcdc0c5663e6ea97a82d87471e25a9553720e5d3","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:8f9bd49f356ee91e4a31c3731a85d881cb1b63c98aeb573ee0f74df0d518aeed","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:0f2aa0b08b8ce5b5075270f29fd79217bd0cfce1885217c44dac8f8953941adb","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
  - {"acceptance_sha256":"sha256:66465497df1b019a9452678898554cfb155cf7c0a1093d5737df21431e302e8f","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: OpenCode Go の認証情報を委任先から隔離して推論を中継する。

## Decisions

- Keep the current parent orchestrator and its final interpretation, authorization, independent-review selection, validation acceptance, lifecycle, commit and publication ownership. The owner requested plan creation following the proposed staged CLI delegation approach; this authoring task does not execute these implementation plans.
- Implement this plan parent-direct in its task-bound worktree because its exact scope includes security or validation authority. Before product edits, prepare the parent-owned execution ledger in parent_direct mode with the required reviewer registry, continuation registry and adversarial preflight. Keep existing review budgets and stop transitions; do not delegate these authority edits to the new Go worker.
- Use Tier 2 for the new external execution boundary. Keep root and generated counterparts aligned in each plan. Default installations stay disabled, and the Codex routing, Sol independent review and existing legacy candidate behavior remain unchanged unless a caller explicitly selects the admitted Go route.
- Support the observed OpenCode 1.18.30 Chat Completions path first. Require an explicit exact model ID and an admitted protocol in local configuration; do not infer entitlement from the catalog, a requested model from a runtime event, or model quality from transport success. Reject unsupported protocols before dispatch; adding Messages or Responses is outside these plans.
- Do not install, upgrade or authenticate a CLI automatically. Automated acceptance uses credential-free local fixtures and does not require a subscription, contact OpenCode Go or consume paid usage. A live check is separately task-authorized and never substitutes for deterministic acceptance.
- A parent-owned process forwards only bounded inference requests for one selected Go model while keeping the upstream API key outside the child environment.
- Keep the upstream key only in the trusted parent transport process, obtained from one runtime-selected credential source. Never copy auth.json, pass the key through worker arguments/environment, persist it, or expose an arbitrary header/URL forwarding service. Diagnostics report credential-source class only.
- Use a per-attempt owner-only Unix socket mounted into the private-network sandbox. A small inner loopback HTTP bridge speaks to that socket; OpenCode receives only the local baseURL and a nonsecret placeholder API key. The socket grants only the already-authorized inference request budget and ends with the attempt.
- Reuse the existing external-service schema and its task, target and effect checks. Bind the provider preflight evidence to the exact parent transport and credential source; evaluate the non-mutating identity preflight separately. Authorize inference as its actual provider operation, never as a repository read. Do not weaken denied effects or require real credentials in tests.
- Use only the fixed upstream https://opencode.ai/zen/go/v1/chat/completions route and an exact allowlisted model ID for this release. Preserve client/session identity headers required by the service without accepting arbitrary forwarding headers. Reject unknown fields that can change destination, authorization or protocol.
- Default to one worker attempt, a 300-second wall deadline, at most 32 upstream requests, a 2 MiB request body and an 8 MiB response/event budget; parent configuration may lower these limits. Disable upstream retries and stop on 401/403/429 or uncertain termination. The fixture covers the observed auxiliary second request without silently allowing a second model.
- Register opencode_go in the existing root policy and in both generated v1/v2 policy branches. The v1 seed stays disabled with empty operation allowlists; v2 registration alone grants neither runtime configuration nor task authorization. Existing project-owned policies are preserved on update; document the explicit local registration needed there rather than silently rewriting them.
- Expose a context-managed parent start operation taking an exact admitted model/protocol, per-request authorization callback and bounded limits; yield only a nonsecret socket endpoint and child configuration. Close idempotently and return a sanitized terminal result. The inner bridge may receive socket/port settings only; later launchers own their child process groups and call close on every terminal path.
- Order the terminal verdict against the start of the upstream send through one shared lock, so no request can begin after a verdict is recorded. Plan 358 reserved a counter before the send, which leaves the interval between admission and connection.request() unguarded. Bound the send with its own socket timeout so holding that lock cannot make cancellation latency depend on the full upstream timeout.
- Register the mirrored transport module in scripts/project_workflow/copier_inventory.py. Plan 355 omitted that path from its write scope, but require_template_manifest_complete() compares the whole tracked template tree, so a new managed module cannot pass the template checker without its three inventory entries. This successor declares the path instead of changing what plan 355 required.
- Forward only the fixed User-Agent and stable per-attempt x-opencode-session identity selected by the parent, along with the permitted content headers; reject downstream attempts to alter that identity. Do not treat child-supplied session headers as authorization.

## Tasks

- [x] Before edits, verify exact write scope and current required specifications, prepare parent-direct execution evidence, and record the unchanged Codex baseline. Do not start a sandboxed candidate worker to edit runner, policy or validation-authority files.
- [x] Implement the parent relay and inner bridge in the mirrored transport module, with explicit start, authorization, streaming, stop and cleanup operations; keep credentials out of serializable state and reject unsafe socket paths.
- [x] Add a fake streaming upstream fixture and a real private-network Bubblewrap test. Prove the child can reach only the mounted inference socket and cannot inspect the synthetic upstream credential through files, environment or proc. Missing required Bubblewrap support is a failed required check, not a skipped successful witness.
- [x] Cover exact model/path/method/header checks, fresh task authorization, redirects, denied provider effects, auxiliary requests, malformed/error/truncated streams, size/time/request bounds, SIGTERM and orphan prevention. Register tests/opencode_go_transport.py in tests/test-sandboxed-plan-worker.py.
- [x] Register the Go provider in root and generated versioned policy seeds without granting configured status; extend tests/validation_tools/external.py to cover missing service/configuration/task authorization, v1 disabled state, v2 denied effects and exact authorized inference targets. Keep the current gate schema and root/template policy checks.
- [x] Update the external-service guidance in both layouts and register the new managed module with the existing inventory/alignment checker. Keep this plan callable transport code with deterministic tests; do not enable a repository helper yet.
- [x] Extend tests/fixtures/orchestration/copier-update-source-inventory.txt and the corresponding tests/copier-update.sh fixtures so their versioned source contains every managed file introduced here. Assert their exact generated locations after copy/update and preservation of existing project-owned policy/configuration; do not weaken the fixture grammar or existing checks.
- [x] Obtain independent review against the exact changed files and the security cases, resolve findings within the existing budget, then run focused validation and the unchanged authoritative suites. Publish the accepted task commit through manage-plan-worktrees.py; do not push.

## Validation Notes

- Pre-admission local evidence: OpenCode 1.18.30 with a temporary empty HOME/config, denied tools and a synthetic loopback provider exited 0; two streamed POST /v1/chat/completions requests selected glm-5.3 and emitted step_start, text and step_finish events. No Go API or real credential was used.
- Requested settings, runtime reports and provider execution are distinct evidence classes. Live entitlement and answer quality remain unverified; deterministic fixture success establishes only the stated implementation conditions.
- Plan 358 stopped at parent_remediation_budget_exhausted. Its one parent-direct remediation round left an accepted Medium finding: a sender admitted by the send counter but paused before connection.request() can still transmit after a later terminal verdict, because the drain waits on that same admitted sender. The parent reproduced it before accepting it. Closing it is a design change to the linearization point, not a repair, which is why this plan exists.
- Plan 355 stopped at scope_drift because scripts/project_workflow/copier_inventory.py is mechanically required and was outside its declared write scope. Its implementation bytes transfer to this plan unchanged through the reconstruction's dirty-path promotion, so the acceptance items and the credential boundary they protect are unchanged.
- The promoted working tree already passed the four focused commands in this manifest and one parent-direct remediation round against seven independent-review findings. Those results belong to the stopped plan 355 ledger. This plan owns a fresh execution ledger, so its own preflight, independent review, focused validation, and authoritative suites are required future witnesses.

- Execution record for this plan's own ledger (run plan359run0, epoch 0, parent_direct). Two adversarial preflights passed with zero failed cases and were recorded as preflight359a and preflight359b. Two independent reviews were used, which is this epoch's full budget, separated by the one permitted parent-direct remediation round.
- Review 1 returned Blocked with one Medium finding at 9/10 confidence: claim_dispatch published STATUS_DEADLINE_EXCEEDED under the state lock alone, so the wall-clock verdict could become visible while another sender held the send guard, and that sender still transmitted. The parent reproduced it independently before accepting it: the sender observed deadline_exceeded at its send point and the fake upstream still counted one complete request.
- The remediation treats per-call-site discipline as the defect rather than the one bypassing call site. status and detail are now read-only properties over private fields, every write goes through _publish or _publish_locked, and _publish always takes the send lock before the state lock. claim_dispatch releases the state lock before publishing, and send_guard gained the last-chance deadline check that was previously missing. The same probe afterwards showed the verdict blocked for the full guarded interval and the sender never observing a terminal status.
- Three regression tests cover the finding, the new guard-level deadline gate, and the structural invariant. Each was mutation-tested on its own and each failed when its defence was removed, so none of them passes vacuously.
- Review 2 returned Accept and reported executing all five requested checks rather than assuming them: the direct field-write search, the record_success call tracing, the guard reentrancy analysis, the dispatch-window race probe, and direct test inspection. It recorded one non-blocking observation, that a concurrent earlier terminal verdict can leave the raised code and the stored aggregate status disagreeing. That is a diagnostic race with no authorization or post-terminal-send consequence, so it is accepted as-is rather than carried as an open finding.
- The reviewer also confirmed that the up-to-five-second cancellation wait is acceptable for this credential boundary, and that it is a per-socket-operation bound rather than a strict total. No cancellation latency SLA is claimed here.
- This runtime cannot record parent_review, focused_validation, or check --operation completion events in parent_direct mode, because those paths require a Codex ReviewPacketStart manifest that this runtime never emits. The reviews, preflights, and validation results above are therefore parent-owned artifacts rather than ledger events, and the same limitation is why plan 358's continuation had to proceed under documented degraded governance.
