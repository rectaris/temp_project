# Execute each frozen evaluation run once in a fresh fixture repository under Bubblewrap with isolated Codex state and bounded evidence

status: in_progress
primary_invariant: Every evaluation run starts from its frozen baseline in its own sandbox with fresh HOME, TMP, XDG and Codex state, receives only a staged auth.json copy and an allowlisted environment, is bounded by its case timeout, and leaves only its own bounded evidence, with no view of other runs or host state.
task_types:
  - harness_evaluation
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"run-sandboxed-plan-worker.py exposes importable build_bwrap_command, which starts from a tmpfs root with --unshare-all, --clearenv and --die-with-parent and shares the network only when asked, and stage_codex_home, which copies only auth.json into a mode-0700 scratch CODEX_HOME.","kind":"existing_mechanism"}
  - {"evidence":"prepare_worker_environment sets scratch HOME and TMPDIR but no XDG directories, and run_bounded_subprocess bounds time and output but takes no stdin, so this plan adds XDG paths and a stdin-capable bounded process runner instead of changing the plan runner.","kind":"existing_mechanism"}
  - {"evidence":"codex-cli 0.157.0 exec --json --ephemeral with gpt-5.6-luna printed JSONL thread.started, turn.started, item.completed agent_message and command_execution items, and turn.completed with usage input_tokens, cached_input_tokens, output_tokens and reasoning_output_tokens; no event named the model.","kind":"bounded_prototype"}
  - {"evidence":"The same CLI with gpt-5.3-codex-spark on a ChatGPT account emitted an error event with status 400 and turn.failed saying the model is not supported, so a model-unavailable run is recognizable from events.","kind":"bounded_prototype"}
  - {"evidence":"CodexBackend.command in worker_backends.py from checked plan 410 builds the runner's exact Codex argv and tests pin it, so an optional JSON-events flag defaulting to off keeps the runner argv unchanged.","kind":"existing_mechanism"}
completion_conditions:
  - run executes every resolved cell once in its frozen order from a fresh fixture repository at its baseline, launching the argv that CodexBackend.command returns with json_events set, and refuses a resolved record whose case, configuration, instruction, registry or environment digests no longer match the current files.
  - Each run executes Codex under Bubblewrap with a writable fixture clone, fresh scratch HOME, TMPDIR and XDG directories, a staged auth.json copy and an allowlisted environment only; a fake Codex in the real sandbox cannot read the host home, this repository, other runs or prior evidence, write outside its clone and scratch, or leave a process behind.
  - A run past its case timeout kills the process group and records timed_out with its elapsed seconds; a turn failure reporting an unsupported or unavailable model records model_unavailable; any other failure records failed; every outcome stays in the run record set with no retry.
  - The execution record keeps elapsed seconds, provider input, cached input, output and reasoning tokens only from turn.completed usage, agent-message and command counts from events, and the CLI version the binary reports, and marks every other value, including the model when no event names it, not_observed.
  - Events and stderr are persisted only after replacing every staged credential value and credential-shaped token with a fixed marker, the redaction report records what was replaced, and a fake Codex that prints its staged credential leaves no copy of it in any retained artifact.
  - Each run keeps only candidate.patch against the baseline including new files, sanitized events.jsonl, sanitized capped stderr, execution.json and a redaction report under runs/<run-id>/ of its experiment, each under 8 MiB, with digests over the persisted bytes, and removes its clone and scratch.
  - agent_eval_execution.py is registered in SOURCE_REQUIRED, both worker_backends.py copies stay byte-identical, and evals/README.md documents run and its isolation limits.
  - The plan runner's default Codex argv, pinned by the existing golden test, and its primary, fallback and correction behavior stay unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:059c0594cac98f55899b0803550343c44651408d79121b06429d0ecbba63627c","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:a28bd2c29ebd83959417590714e14e39528d09574de761ee22aa222cf7356454","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:efae1eaf0fb4d09753c580c8c65cdc232114697c5a0d4553be78fd1870830d4f","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:22db1653fac5d11b66c9ca8a1393f082c8153f8309af4d23f74cf90233b8db5b","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:59ebf72aaa3b7f53046cc3dbce0e32cd349f0b9e8b9da5f4d8ac6ba6dda98f08","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:63837cabb11c023b6fe4c5bcf68dcedd9e5108f0df61e8a2471b4f9d527887d5","witness":"python3 tests/test-agent-eval.py"}
  - {"condition_sha256":"sha256:2f2086b855f8a88e98ee89dcfde3cab5c22a2b0bc5d12d715beeff8287f5a593","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:d645dbdec9d29f2c4ed77ceaad3dd270cd7a99350cc7fac95d4c549be0917628","witness":"python3 tests/test-sandboxed-plan-worker.py"}
write_scope:
  - scripts/project_workflow/agent_eval_execution.py
  - scripts/agent-eval.py
  - tests/test-agent-eval.py
  - evals/README.md
  - scripts/project_workflow/copier_inventory.py
  - scripts/project_workflow/worker_backends.py
  - template/.project-agent-workflow/scripts/worker_backends.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/agent_log_manifest.py
  - docs/plan/checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md
  - docs/plan/checked/2026/09/16-31/416-freeze-evaluation-experiments-before-execution.md
required_specs:
  - docs/agent/SPEC_HARNESS_EVALUATION.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-agent-eval.py
  - python3 scripts/check-copier-template.py
  - python3 tests/test-sandboxed-plan-worker.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Each repetition starts from the exact same Git baseline with isolated HOME, TMP, XDG and agent state, and no run sees prior transcripts, reports, other configurations' outputs or agent memory.
  - Missing telemetry remains not_observed, and token counts are taken only from provider-reported usage, never derived from bytes.
  - Failed, timed-out and unavailable-model runs remain in the run record set, and production plan-runner behavior is unchanged unless evaluation is explicitly invoked.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:87aa108b2c6ccd4d354eda141752413f9e54dda27d8f7b4f3b12d908d6096601","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
  - {"acceptance_sha256":"sha256:3e2ef9fc2ca5843a49ab0e26e4dc2820a3ba588d9352c00577de2e4655ce41c3","stage":"focused","witness":"python3 tests/test-agent-eval.py"}
  - {"acceptance_sha256":"sha256:6696ff643e0eed646bf0419ba1e4f479198923761044b60320734346f7ede647","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - docs/plan/backlog/416-freeze-evaluation-experiments-before-execution.md must reach a checked archive before this plan starts, because run consumes its resolved records.
checked_summary_ja: 確定した評価の実行を、新しい fixture のリポジトリと分離した Codex の状態で Bubblewrap の中で一回ずつ行い、限られた証拠を残す。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger, because this plan starts model processes with a staged credential and network access.
- Reuse build_bwrap_command and stage_codex_home from run-sandboxed-plan-worker.py through importlib instead of copying them; add a stdin-capable bounded process runner with a process-group kill in agent_eval_execution.py, and change no plan-runner function.
- Add json_events: bool = False to CodexBackend.command; True appends --json, and the default argv the plan runner uses stays exactly as plan 410 pins it.
- Mount only the writable fixture clone, the run scratch and the staged CODEX_HOME. Set HOME, TMPDIR and XDG_CONFIG_HOME, XDG_CACHE_HOME, XDG_STATE_HOME and XDG_DATA_HOME inside scratch, pass PATH and locale only, and share the network because the provider needs it; record that network mode in the run record.
- Keep one run per sandbox process and one fresh scratch per run. Never reuse a scratch, a clone, a Codex session or a cache between runs, which is what the cold cache policy states.
- Classify outcomes from events and exit status: completed needs exit 0 and turn.completed; an error or turn.failed naming an unsupported, unavailable or inaccessible model is model_unavailable; the case timeout is timed_out; everything else is failed. Never retry or fall back to another model.
- Read tokens only from turn.completed usage with provenance provider. Read the CLI version from `codex --version` before the run. Leave observed model not_observed unless an event names it.
- Store runs under .agent-artifacts/evaluations/<experiment-id>/runs/<run-id>/ and keep events.jsonl local; the execution record binds its digest instead of copying transcript content.
- Prove isolation with an adversarial fake Codex inside the real Bubblewrap sandbox on every host. CI installs no Codex, and no test calls a provider; the real-model replication run happens after plan 417 as an evaluation operation outside numbered plans.
- Redact before persisting: replace the staged auth.json values and credential-shaped tokens in events and stderr with a fixed marker, write the per-run redaction report that SPEC_AGENT_LOGGING.md requires, and compute every evidence digest over the persisted sanitized bytes, which plan 417 consumes unchanged.

## Tasks

- [ ] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the unchanged plan-runner suite result.
- [ ] Add json_events to CodexBackend in both copies.
- [ ] Implement run: digest recheck, fresh fixture clones, the sandbox mounts and environment, staged auth, the bounded process runner, outcome classification, telemetry, artifacts and teardown.
- [ ] Add fake-Codex cases for completion, timeout, unavailable model, failure, token parsing, missing usage, a printed staged credential, isolation escapes, lingering processes and patch extraction with new files.
- [ ] Register the module and document run in evals/README.md.
- [ ] Record a passing adversarial preflight, obtain independent review through a fresh read-only reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26, 「提案の方針で進める。」, fixed the root-only controller and the evidence location. Implement in a new conversation session from the published plan, per the owner's question about separate sessions.
