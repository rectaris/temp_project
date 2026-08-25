# AGENTS.md

Agent entrypoint for `project-agent-workflow`.

## Scope

This repository packages reusable coding-agent project management, file routing, validation, and file-management templates.

## Rules

- Keep `SKILL.md` concise; move detailed guidance into `references/`.
- Keep installable repo files under `template/`.
- Keep `copier.yml` as the long-term generation/update interface.
- Treat non-destructive Copier evolution as a repository invariant: supported copy and update paths must preserve project-owned product code, policy, configuration, plan history, and validation behavior, and must stop on unresolved conflicts, rejection files, or unclassified tracked-file deletion.
- Keep deterministic checks in `scripts/` or `tests/`.
- Use `references/orchestration.md` for bounded delegation triggers, final ownership, and safety boundaries.
- Do not add project-specific `supportcard-status` facts to generic templates.
- When writing or editing Japanese prose in this repository, follow `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.
- When changing Japanese writing policy for generated projects, keep `docs/agent/SPEC_JAPANESE_TECH_WRITING.md` and `template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` semantically aligned, or state the intentional difference in the change.
- Use `docs/agent/spec-index.yaml` to route root-level agent policy when the task concerns planning, logging, compression, decision audit, user-facing communication, or Japanese prose.
- Route requests to inspect or remove local linked worktrees or their local branches through `docs/agent/SPEC_GIT_RETIREMENT.md` and the project-owned `docs/agent/git-retirement.yaml` configuration.
- Keep raw agent logs and large agent artifacts local under `.agent-logs/` and `.agent-artifacts/`; do not commit them.
- Treat external transcript logs as primary full-turn evidence when available, and repo-local hook event logs as best-effort corroborating evidence.
- Record missing transcript or hook sources explicitly in run manifests.
- Use `.codex/hooks/agent_log_event.py` as the root best-effort Codex lifecycle event logger when Codex hooks are active; keep raw outputs under `.agent-logs/`.
- Use run manifests, search, excerpts, and optional context compression before loading large raw logs.
- Read `AGENTS.md`, `docs/agent/`, validation policy, and security policy directly; do not route normative instructions through compression.
- Run decision audit before creating or materially updating active plans when meaningful design, storage, validation, lifecycle, security, or artifact-boundary choices remain open; keep the full audit out of `docs/plan/active`.
- Keep active plans as executable agent instructions. Record final accepted decisions only, not recommendation matrices or debate transcripts.
- Use the repo-local `.codex/skills/decision-audit` skill when available; keep `docs/agent/SPEC_DECISION_AUDIT.md` as the normative root policy.
- Before introducing a new domain or workflow label in design, investigation, remediation, causal-summary, or naming work, fix its concrete referent and preserve unresolved facts according to `docs/agent/SPEC_REFERENT_FIRST.md`; use `.codex/skills/define-referents-first` for the operational workflow. In chat naming work, show an unnamed referent and uncertainty stage before any candidate or controlled term.
- Use repo-local generic Codex skills such as `.codex/skills/implementation-guidelines`, `.codex/skills/mcp-ops`, `.codex/skills/linear-ops`, `.codex/skills/graph-memory`, and `.codex/skills/plan-archive` only as auxiliary workflow guidance; keep project-specific values in `docs/agent/` policy files.
- Use `scripts/run-sandboxed-plan-worker.py` for writable sequential-plan implementation; keep `.codex/agents/sequential_plan_worker.toml` read-only and apply only parent-admitted candidate patches. Every writable delegated plan must declare one nonblank `primary_invariant` and exact file paths in `write_scope`; directory prefixes, protected inputs, and validation-authority paths fail before worker start. `preservation_scope` records exact dirty product paths that restructuring must retain, but it never grants candidate generation, validation, apply, staging, or commit authority; reject any overlap with `write_scope`. Require a canonical network `remote.origin.url`; the runner supplies a freshly derived, repository- and plan-bound contract as read-only input for each attempt.
- Require one bounded worker completion receipt for every initial, fallback, custom, and correction attempt. Cross-link it to the verified contract, process status, and Git-derived candidate facts; treat every worker claim as advisory and retain parent-only lifecycle, validation, apply, commit, archive, and reporting authority.
- Review an admitted candidate diff and critical invariants before parent-authorized focused validation, then run the authoritative validation suite exactly once for an otherwise acceptable candidate. After one initial generation and two rejected isolated corrections, require a strategy change; bounded parent implementation is permitted for inseparable high-judgment work or exhausted correction budget with explicit scope, independent review, and unchanged acceptance gates.
- Require a new or materially updated in-progress integration plan to declare `validation_witness_schema: 1` and map each acceptance item exactly once in `validation_witness_map`, bound by its SHA-256 digest to its earliest parent-owned static, focused, or authoritative witness. Keep a pre-schema project-owned integration plan readable during Copier updates only when its exact plan bytes and acceptance digests still match one successor in its existing versioned replan contract and the source archive remains `replanned`. Permit a static witness only for its named enforced predicate, reject missing coverage, a focused command labeled authoritative, and an authoritative-only witness without one bounded reason that a narrower safe preflight is unavailable; the map must never remove or weaken the authoritative `validation` suite.
- Treat `.project-agent-workflow-migration/validation-witness-provenance-v1.json` as the single-use, migration-owned `validation-witness-migration-provenance-schema: 1` record. Only the v1.4.5 before-update migration may create the canonical snapshot from a clean committed HEAD while one original live guardian holds a 256-bit capability whose capability commitment, repository identity, source commit, snapshot digest, attempt id, socket path, and one-hour expiry are bound in mode-0600 Git-local attempt state. Publish that state only through `prepared` and `pending`; the matching after-update stage must reproduce the exact snapshot and complete a fresh challenge-response through the confined, race-checked socket path. The socket pathname is not identity evidence; opening the capability commitment and verifying its keyed proof establish the same live guardian, which must durably transition the attempt to `consumed` before acceptance. If the final response is lost, only the same live guardian may resume the same consumed attempt; `consumed` remains terminal after that guardian exits. Permit `recovering` only before the updated policy marker exists, after proving the original guardian is no longer live and the committed source, repository identity, reconstructed snapshot or allowed partial publication, and bounded attempt state still match; recovery removes the stale pre-boundary attempt instead of authorizing compatibility. Expiry rejects after-stage authorization but permits this verified pre-boundary recovery. Reject missing, stale, unsafe, forged, cross-clone, or replayed after-stage evidence; reject symlinked or hard-linked regular-file evidence and a socket path that is not confined or changes type or device/inode/change-time while connecting. Never treat the snapshot or attempt state as product acceptance evidence or as a validation witness by itself. Copying repository and Git-local files without the original live guardian fails; an unrestricted same-user actor that can replace every local process and file is outside this guarantee.
- After authoritative validation fails, record `diagnosis_required` before any repair classification. While it is active, permit only bounded parent-owned read-only reproduction and append-only diagnosis evidence; block worker, correction, validation, apply, completion, archive, and repair-plan operations until one `confirmed` diagnosis with an independent-review receipt binds the exact failed operation, observed exit status, and one affected invariant. Then transition only through the existing `repair_required` or `replan_required` classification; inconclusive or disputed evidence remains stopped.
- Record `repair_required` only for one independently repairable defect with bounded write and validation scope, unchanged source-plan scope and validation authority, unchanged invariant boundaries, unchanged source acceptance and safety conditions, unchanged external-effect authority, and no coupled independent invariants. Stop the affected execution run, keep the source plan `deferred`, create a separate bounded repair plan, and resume the source plan only through a fresh run after that repair is checked.
- Mark the active plan `replan_required` and stop execution when scope/spec/security boundaries drift, multiple independently validatable invariants remain coupled, authoritative validation reveals a change that requires reconstructing source-plan boundaries, methods, validation authority, or acceptance mapping, the candidate correction budget is exhausted, or two parent-direct remediation rounds still leave High or Medium findings. Reconstruct only plan boundaries, ordering, implementation methods, and validation methods; preserve user requirements, accepted safety conditions, and source acceptance items unless the user explicitly authorizes a requirement change. Never relabel requirement, authority, or security-boundary drift as an independent repair.
- For high-risk or correction-capable execution, use the parent-owned plan execution ledger outside the repository, record independent-review receipts for parent-direct remediation and independent-repair classification, and pass the ledger to every sandboxed runner operation so `repair_required` and `replan_required` stop before further worker or source effects. Never reopen a stopped ledger run.
- Start one writable attempt only after the ledger rechecks its exact plan and source baseline and atomically claims the accepted predecessor leaf for one successor. Bind the ledger attempt id through the worker contract, receipt, manifest, and lifecycle; close the attempt through a parent-authored accepted, correction-requested, or rejected transition. An accepted close requires the exact admitted patch in one clean descendant commit, and no second successor or overlapping writable attempt may consume the same chain leaf. Keep concrete findings outside the ledger, use only the fixed review reason codes and evidence digests, and allow concurrent helpers only when they remain independent, bounded, and read-only.
- Bind each staged review to the immutable tuple of writable attempt id, fully verified admitted candidate-manifest digest, and admitted patch digest, and bind its packet to the verified worker receipt and current required specifications. Count one initial review and one rereview against that tuple rather than mutable lifecycle bytes; require the latest round to clear High and Medium findings, accepted closure to have that review, and the accepted candidate or parent-direct checked commit to contain only the reviewed in-scope patch.
- Initialize one parent-owned reviewer session registry outside the repository and pass it to every bounded review, checkpoint issuance, and checkpoint claim. Admit each runtime-proven reviewer-session digest once under the registry lock, bind exact crash recovery to the execution genesis, and bind inbound checkpoints plus the registry identity, event count, and event-chain digest into each child ledger instead of carrying cumulative reviewer lists.
- Before continuing a chain from a schema-1 checkpoint, use the parent-owned checkpoint migration command to verify its original issuance and review receipts, backfill those reviewer admissions into the canonical registry, and append a linked migration event; never strand or silently reinterpret an issued legacy checkpoint.
- Route the writable runner from the plan's separate `implementation_risk` and `implementation_ambiguity` fields: GPT-5.3-Codex-Spark medium only for low/low, GPT-5.6-Terra medium when neither is high and at least one is ordinary, and refuse either high. Reserve Sol for independent review. Allow exactly one fresh isolated GPT-5.6-Luna max attempt only when the Codex CLI itself reports a bounded usage limit, rate limit, unavailable-model, or denied-model-access error; do not fall back for other failures.
- Before submitting a substantive progress update, proposal, explanation, blocking report, or final summary, follow `docs/agent/SPEC_USER_COMMUNICATION.md` and use `.codex/skills/write-for-reader` for its operational workflow.
- When creating or updating Codex skills, follow `docs/agent/SPEC_SKILL_AUTHORING.md`.
- Classify every change as Tier 0, Tier 1, or Tier 2 under `docs/agent/SPEC_PLAN_WORKFLOW.md` before creating plan artifacts, record `implementation_tier` in the active plan, and keep Tier 0 and Tier 1 work out of the restructuring contract.
- Validate with `scripts/lint-project-workflow.sh` and `tests/smoke.sh` before completion.
- Use Git for all changes.
- Keep commits granular and scoped to one meaningful work unit.
- Do not stage unrelated files.
- Do not rewrite history unless explicitly requested.
- Preserve user changes you did not make.
- Before deleting generated backup files such as `*.backup`, `*.orig`, or `*.pre-*`, inspect and preserve or report useful prior state.
- Commit after successful validation unless the user requested otherwise or a concrete dirty-worktree blocker prevents it.
- Do not push unless the user explicitly requests it.

## CI Autofix Rules

- Codex must make minimal changes when repairing CI failures.
- Codex must not change unrelated behavior.
- Codex must not weaken tests to make CI pass.
- Codex must not delete failing tests unless the user explicitly requests it.
- Codex must not modify secrets, deployment credentials, or production settings.
- Codex must prefer fixing root causes over skipping checks.
- Codex must stop and report when the failure is due to missing secrets, external service outages, or environment-only issues.

## Delegation Safety and Ownership

- Delegate proactively without requiring a separate per-task user instruction only when a bounded helper can return independently useful output and expected context reduction, parallelism, or review value exceeds coordination cost; repository breadth alone is insufficient.
- Keep final ownership in the main agent for interpretation, final integration, validation acceptance, planning updates, commits, and the final report/completion reporting.
- Do not delegate short deterministic commands (including pass/fail commands), direct user clarification, final policy judgment, authorization decisions, external writes, secret handling, or destructive changes unless an explicit external policy grants that authority.
- Keep helper delegation bounded by `write_scope`, keep context files read-only, and keep final acceptance and reporting in the main session.
- Final report must state whether helpers were used; if used, include role, write scope, and the main-session acceptance decision path.
- Treat helper output as advisory until validated in the main session.

## Reports

- State touched repository: `temp_project`.
- State link changes.
- Report validation and the commit hash, or the exact dirty-worktree blocker when a commit cannot be made.
