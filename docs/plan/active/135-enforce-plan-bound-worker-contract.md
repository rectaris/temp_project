# Enforce one immutable plan-bound worker contract

status: in_progress
task_types:
  - planning_docs
  - referent_first
  - security
  - skill_authoring
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
primary_invariant: start one isolated writable attempt only from a freshly verified immutable plan projection whose explicit write paths cannot reach protected or validation-authority inputs
write_scope:
  - AGENTS.md
  - CHANGELOG.md
  - .codex/skills/sequential-plan-orchestrator/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
  - tests/test-validation-tools.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/active/134-freeze-worker-contract-scenarios.md
  - docs/plan/replanned/2026/08/16-31/113-generate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/validation.md
  - tests/fixtures/orchestration/worker-contract-scenarios.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Generate one versioned worker execution contract deterministically from the exact committed active-plan bytes admitted for one initial or correction attempt; bind it to the repository identity, source HEAD, plan path, plan digest, orchestration run identifier, and attempt lineage.
  - Include only the plan's primary invariant, normalized write scope, context files, required specifications, acceptance items, focused-validation commands, explicit exclusions, and hard stop conditions needed by that attempt.
  - Require every writable delegated plan to declare exactly one nonblank `primary_invariant`, reject a missing or ambiguous invariant before worker start, and preserve compatibility for plans that are parsed or archived without writable delegation.
  - Keep the active plan and directly read normative specifications as the implementation source of truth; require the worker to read them, and treat the generated record as a supplemental bounded projection that cannot override, omit as satisfied, or amend source requirements.
  - Validate the record schema, size, normalized repository-relative paths, digests, identity, lineage, and exact equality to a fresh derivation immediately before worker invocation; fail closed on any mismatch, unknown field, duplicate item, symlink escape, or plan change.
  - Mount or copy the record into the isolated worker boundary as read-only input and prevent the worker from changing the active plan, generated record, runner, validation authority, source worktree, or parent-owned execution state.
  - Do not include prompts, worker output, environment values, credentials, host-specific absolute paths, raw logs, or undeclared repository files in the record.
  - Build the worker prompt from fixed repository policy plus the verified structured record instead of a separately maintained restatement of plan details; do not create a second manual source that can drift from the plan.
  - Preserve existing isolated-clone, no-hardlink, clean-source, object-database, model-routing, correction-budget, candidate-admission, validation-order, and external-effect boundaries.
  - Keep root and generated runner behavior byte-identical, keep root and generated orchestration policy and Skill semantics aligned after path normalization, and preserve project-owned files through supported Copier copy and update paths.
replan_source: docs/plan/active/113-generate-plan-bound-worker-contract.md
replan_contract: docs/plan/replanned/contracts/113-generate-plan-bound-worker-contract.json
integration_gates:
  - plan 134 must be checked and its exact fixture digests copied into this plan before implementation starts
  - directory-prefix write_scope entries must fail before worker start and explicit missing non-authority paths may represent new files
  - plan 136 must run the unchanged holdout only after this implementation is otherwise review-ready
successor_plans:
  - docs/plan/active/134-freeze-worker-contract-scenarios.md
  - docs/plan/active/135-enforce-plan-bound-worker-contract.md
  - docs/plan/active/136-integrate-plan-bound-worker-contract.md
inherited_acceptance_digests:
  - sha256:018029e6bdbccfad54ba0fbff30086b4b44b66a7aaf6f5594bd83888f5001774
  - sha256:4c502f3bd90348bdc59aac577a337138d2aa6cf0271e3ec48031d2065005cf25
  - sha256:4a6fac9ef3c6aab2d6bae45781039ac3ebda91510a3bcd90d5bfd5154bef50d9
  - sha256:8906a81c8ab0aef8c31d4302d17f9123c291d2c70a9514dbae13046985bce018
  - sha256:7f7246745d04b98585178c14b1e9ba9a8f34ef100d1dbdb517ef008472467313
  - sha256:eafceb41a6a90a1ec5824d8e199e4dcccbf080384ef9d322459f66e8f5ec14f8
  - sha256:3f7161430933f10ffcd7c9cc644455f883cbeb0a0dc4048bbba8538f0e05a6bc
  - sha256:fbd0c6713ded62fe841a3bf84241e307f5a5c294838c784c2c1ba8b04a95646e
  - sha256:9b5f72cb26b3b91826edda511243eecc9f0e5c62034524576d94dda1e28f16ec
  - sha256:bfa8cb8b800056e0282e4d34f739d40f36cd5957f884d7638c9bc8fe03435473
checked_summary_ja: worker起動前にplan由来の契約と明示的な書込pathを検証し、保護対象や検証権限へ到達できる書込を許可しない。

## Decisions

- Refuse directory-prefix entries for writable delegation; each delegated write entry must be one explicit normalized path.
- Permit one exact missing non-authority path as a declared new file only after validating its parent path, protected-input classification, and validation-authority classification before mounting.
- Derive the bounded contract from committed plan bytes and validate exact schema, identities, uniqueness, size, and fresh equality immediately before each initial or correction invocation.
- Mount the contract and every authoritative input read-only; keep the source repository and parent state outside writable mounts.
- Treat the frozen tuned scenarios as read-only evidence; verify only the recorded holdout digest and do not load or inspect the holdout bytes while implementing tuned behavior.
- Keep `python3 tests/test-sandboxed-plan-worker.py` tuned-only; do not invoke the explicit `--include-holdout` behavior selector in this plan.
- Use bounded parent implementation and independent review because runner, tests, and policy are validation authority.

## Tasks

- [ ] Implement exact-path delegated shadows, safe explicit new-file handling, and pre-start protected/authority rejection.
- [ ] Implement versioned contract derivation, exact validation, read-only mounting, and initial/correction lineage binding.
- [ ] Replace duplicated prompt plan details with fixed policy plus the verified contract while retaining direct plan/spec reads.
- [ ] Align root and generated runner, policy, Skill, checks, and Copier behavior without changing frozen fixtures.
- [ ] Review the bounded parent diff, run tuned focused validation, obtain independent review, run the authoritative suite once without the holdout, and archive the accepted implementation.

## Validation Notes

- Plan 134 is a hard predecessor; its fixture paths are intentionally absent from this write scope.
- The source Plan 113 acceptance text is preserved exactly.
