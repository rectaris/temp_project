# Fall back when the preferred sequential worker model is unavailable

status: checked
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - .codex/agents/sequential_plan_worker.toml
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/067-root-external-write-policy.md
  - template/.codex/agents/sequential_plan_worker.toml
  - .agent-artifacts/decision-audits/sequential-worker-model-fallback.md
  - .agent-artifacts/referent-contracts/sequential-worker-model-fallback/contract.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Keep gpt-5.3-codex-spark with medium reasoning as the preferred default for the sandboxed sequential plan worker, without changing the read-only built-in agent profile.
  - A nonzero Codex CLI result whose own error line deterministically reports a usage limit, rate limit, unavailable model, or denied model access starts exactly one fallback attempt; all other nonzero results stop without fallback.
  - Run the fallback attempt with gpt-5.6-luna and max reasoning from the same source HEAD in a new isolated clone, scratch directory, writable-shadow set, staged authentication copy, and ephemeral Codex session.
  - Never reuse changes, Git configuration, caches, output-last-message state, or another writable artifact from the unavailable preferred-model attempt.
  - Keep authentication failures, network failures, refusals, implementation failures, validation failures, sandbox denials, custom-worker failures, and unclassified errors fail-closed without fallback.
  - Preserve explicit CLI overrides for the preferred model and reasoning effort, and add explicit fallback model and reasoning overrides plus a switch that disables automatic fallback.
  - Record every attempted model, reasoning effort, return code, stdout and stderr paths and digests, selection result, and bounded fallback reason code in the successful candidate manifest without embedding raw output or credentials.
  - Keep failed-attempt raw stdout and stderr only in the existing local output-artifact boundary, and do not copy them into plans, commits, or the manifest body.
  - Apply the same fallback behavior to the root and generated runner through byte-identical implementations and keep actual OpenAI calls out of deterministic tests.
  - Add deterministic tests proving preferred success, recognized unavailability fallback, fresh-clone isolation, fallback success provenance, fallback failure, nonavailability failure, custom-worker single-attempt behavior, CLI overrides, and fallback disablement.
  - Update root and generated orchestration guidance, static checks, smoke coverage, and the changelog to describe the preferred and fallback configurations and the strict trigger boundary.
  - After validation and archival, return plan 067 to in_progress and use the updated sandboxed runner to implement it.
checked_summary_ja: 逐次plan workerでGPT-5.3-Codex-Sparkを優先し、利用不能時だけ新しい隔離環境のGPT-5.6 Luna maxへ一度切り替える。

## Context

The preferred GPT-5.3-Codex-Spark worker could not start plan 066 because its usage limit was exhausted, and the runner stopped without a candidate patch.

The user requires an automatic fallback to GPT-5.6 Luna with max reasoning and explicitly authorizes one parent-session implementation of this prerequisite.

Official OpenAI model documentation confirms that `gpt-5.6-luna` supports `max` reasoning effort.

## Decisions

- Treat only a bounded Codex CLI availability classification as fallback eligibility; do not retry arbitrary worker failures.
- Start the fallback from the same committed source HEAD but a new clone and scratch boundary.
- Keep GPT-5.3-Codex-Spark medium as the preferred built-in profile and runner default.
- Use GPT-5.6 Luna max for one automatic fallback attempt.
- Preserve both attempts as local evidence and identify the selected attempt in the manifest.
- Keep custom workers outside model fallback routing.
- Use the user's one-time exception for direct parent implementation of this plan, then restore sandboxed worker implementation for plan 067.

## Tasks

- [x] Add a bounded preferred-model unavailability classifier and isolated fallback attempt lifecycle.
- [x] Extend manifest provenance and CLI controls without exposing raw output or credentials.
- [x] Add focused deterministic unit and integration coverage using fake local Codex executables.
- [x] Align root and generated runner, policy, Skill, checks, smoke assertions, and changelog.
- [x] Run every required validation command and record the results.
- [x] Archive this plan, restore plan 067 to in_progress, and resume it through the sandboxed runner.

## Validation Notes

- `python3 tests/test-sandboxed-plan-worker.py`: passed, 31 tests.
- Runner self-test, root policy check, Copier static check, change-aware validation, workflow lint, generated-project smoke, and `git diff --check`: passed.
- Root and template runners are byte-identical. Deterministic fake-Codex coverage verifies eligible fallback, fail-closed mixed and unrelated errors, fresh-clone state, hidden host and prior-attempt paths, provenance, CLI overrides, disablement, and failure cleanup.
- A read-only change review found four isolation, classification, wording, and failed-output retention gaps; all were corrected and the reviewer accepted the revised implementation with no remaining actionable findings.
- Actual fallback execution is deferred only until this plan is archived and plan 067 is restored to `in_progress`, as required by the lifecycle boundary.
