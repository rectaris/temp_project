---
name: sequential-plan-orchestrator
description: Execute numbered files in docs/plan/active sequentially by delegating one bounded plan at a time to the generated sequential_plan_worker agent, then reviewing, accepting, and updating dependent plans. Use when a project needs parent-controlled orchestration of multiple active implementation plans.
---

# Sequential Plan Orchestrator

Process active plans as a parent-owned sequence. Keep implementation in the worker, keep acceptance and lifecycle decisions in the parent, and stop when a plan cannot be safely accepted.

## Workflow

1. Enumerate `docs/plan/active/<number>-<name>.md` files and sort by the integer prefix.
   Stop on malformed names, duplicate numbers, ambiguous or blocked plans, or missing required inputs.
2. Read the selected plan, every required spec, and the active-plan index before delegation.
3. Verify `scripts/run-sandboxed-plan-worker.py` is available and keep the built-in `sequential_plan_worker` profile read-only.
   Stop if the sandboxed runner is unavailable.
4. Admit one admissible implementation slice before running `scripts/run-sandboxed-plan-worker.py run <plan>`. It must establish one invariant, be independently reviewable and validatable, and retain an explicit later integration gate; a broad plan is not itself a valid candidate boundary. Delegation must produce independently useful output whose expected context reduction, parallelism, or review value exceeds coordination cost.
   Run the worker to create a candidate patch and manifest from an isolated clone. The runner mounts the clone read-only and over-mounts writable shadows only for normalized `write_scope` entries; temporary artifacts belong under the worker scratch directory.
   Pass the selected plan path and keep the plan's `context_files` read-only.
   Optional scalar plan fields `implementation_risk` and `implementation_ambiguity` accept `low`, `ordinary`, or `high`; only absence defaults to ordinary and malformed present values fail closed. Low/low selects `gpt-5.3-codex-spark` medium, an ordinary input without a high selects `gpt-5.6-terra` medium, and either high refuses writable delegation. Explicit nonblank overrides remain available, but Sol is rejected for both preferred and fallback writable attempts and remains reserved for independent review. If the Codex CLI's own error line classifies the selected attempt as a usage limit, rate limit, unavailable model, or denied model access, the runner may start exactly one `gpt-5.6-luna` max fallback from the same source HEAD in a new clone and scratch boundary. No other failure is fallback-eligible.
   Pass a locked lifecycle-state path outside the repository and an explicit nonblank run identifier to run, correct, validate, and apply. For a multi-plan run, optionally pass a separate availability-state path with the same identifier. The lifecycle ledger linearizes one candidate leaf, corrections, validation, and apply; the availability state stores only model/reason codes. Treat telemetry as measurement only.
5. Inspect the candidate patch, manifest, and worker result.
   Treat them as advisory. Complete deterministic admission, parent diff review, and critical-invariant review before authorizing `scripts/run-sandboxed-plan-worker.py validate <manifest> --suite focused`; the validation operation uses a separate fresh network-isolated review clone per command and the unchanged committed plan. Reject candidate changes to validation-authority paths and use bounded parent implementation plus independent review for those paths. Candidate generation and correction do not run plan validation.
6. Reject and stop on a blocker, missing input, an out-of-scope path, an unrelated change, or failed required validation. For a localized parent-review rejection only, write a bounded correction brief outside the repository and run `scripts/run-sandboxed-plan-worker.py correct <plan> <prior-manifest> <brief>`.
   A correction verifies the prior candidate, applies its patch only inside a fresh clone, hides prior artifacts, mounts the brief read-only, and emits an aggregate patch against the original HEAD. Reuse the same availability state and run identifier. Permit at most two consecutive correction rounds; after that require strategy change. Do not retry an unclassified, semantic, or validation failure or continue to the next plan.
   When a mandatory restructuring trigger is present, mark the plan and active index `replan_required`, record only bounded reason codes, and stop candidate generation, correction, validation, apply, completion, and archival. Preserve the exact requirement and acceptance baseline; do not silently rewrite it as part of strategy change.
7. On acceptance, apply the candidate with `scripts/run-sandboxed-plan-worker.py apply <manifest>`, then update only the assigned plan's concise validation notes and affected later plans' decisions, targets, dependencies, or validation conditions.
   Before apply, authorize the same validation operation with `--suite authoritative` exactly once for an otherwise acceptable candidate. A failed focused or authoritative command stops without model fallback.
   Keep detailed logs and large evidence under `.agent-logs/` or `.agent-artifacts/`.
8. Repeat for the next numeric plan only after acceptance.
   Finish with consolidated validation and remaining-risk reporting.

## Boundaries

- The worker may modify only the assigned plan's explicit write scope: unlisted clone paths, including `.git`, are read-only during execution, and the parent independently admits only an in-scope candidate patch.
- The parent may modify orchestration metadata, affected active-plan instructions, concise validation notes, and local evidence references.
- After two rejected corrections, require an explicit strategy change. Bounded parent implementation is permitted only for inseparable high-judgment work or exhausted correction budget, with explicit write scope, a clean worktree, no authority expansion, independent change review, and the same authoritative validation.
- Mandatory restructuring triggers are scope/spec/security-boundary drift, multiple independently validatable invariants in one slice, a post-authoritative design change, exhausted candidate corrections, and two parent-direct remediation rounds with unresolved High or Medium findings. Time is telemetry only. A replan may change boundaries, ordering, implementation methods, and validation methods, but requirements or accepted safety conditions require explicit user authorization.
- Do not process the next plan, spawn descendants, perform external-service writes, weaken tests, commit unrelated changes, or bypass `scripts/run-sandboxed-plan-worker.py`.
- Do not copy full decision audits, raw logs, or large artifacts into `docs/plan/active`.
- Inspect every model attempt recorded in the manifest. Failed-attempt stdout and stderr remain local artifacts and must not be copied into plans or commits.
