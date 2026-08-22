# Enforce one structured worker completion receipt

status: replan_required
replan_reason_codes:
  - parent_remediation_budget_exhausted
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
parent_direct_reason: the root and generated runners, policy checks, and receipt tests are parent-owned validation authority
primary_invariant: accept a worker completion receipt only as bounded advisory evidence cross-linked to one isolated attempt and its admitted candidate while retaining every lifecycle and validation decision in the parent
write_scope:
  - AGENTS.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - tests/copier-update.sh
  - tests/smoke.sh
  - tests/test-sandboxed-plan-worker.py
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/replanned/2026/08/16-31/114-validate-structured-worker-completion.md
  - docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md
  - docs/plan/checked/2026/08/01-15/074-isolated-candidate-correction.md
  - docs/plan/checked/2026/08/01-15/078-plan-execution-budget-ledger.md
  - references/validation.md
  - tests/fixtures/orchestration/worker-completion-receipt-scenarios.json
  - tests/fixtures/orchestration/worker-completion-receipt-holdout.json
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
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/run-sandboxed-plan-worker.py self-test
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
  - git diff --check
acceptance:
  - Require plan 136, the accepted successor for plan 113, to be checked and archived before implementation starts, and consume its verified worker execution contract identity rather than reconstructing plan authority from worker output.
  - Use plan 136's exact checked archive path before worker start; treat this as a dependency-path refresh only, rerun plan checks, and do not change accepted requirements or broaden scope.
  - Define one versioned, size-bounded worker completion receipt for each successful or failed initial and correction attempt, written only inside the isolated attempt output boundary.
  - Bind the receipt to repository identity, source HEAD, plan path and digest, worker execution contract digest, orchestration run identifier, attempt identifier, correction lineage when applicable, candidate patch digest when emitted, and normalized changed paths.
  - Require bounded fields for claimed acceptance evidence, commands attempted with observed exit status, blockers, residual risks, and an explicit out-of-scope-change declaration; allow empty evidence only when the attempt reports failure before a candidate exists.
  - Keep command and evidence entries declarative and size-limited; never store prompts, free-form output bodies, environment values, credentials, raw logs, patches, or host-specific paths in the receipt.
  - Validate schema, exact fields, types, bounds, normalized paths, identity, lineage, cross-linked digests, and consistency with the admitted candidate before using the receipt; fail closed on missing, duplicate, unknown, malformed, oversized, stale, replayed, or symlink-escaping content.
  - Treat every receipt claim as advisory: the parent must independently inspect the admitted diff and critical invariants, verify changed paths from Git, choose validation from parent-owned plan data, and retain sole acceptance, apply, commit, archive, and completion-report authority.
  - Never allow a worker assertion of success, test passage, scope compliance, or acceptance coverage to advance candidate lifecycle or plan execution state without the existing parent-owned transition and evidence checks.
  - Preserve worker process exit status and bounded sanitized diagnostics separately from receipt validity so malformed reporting cannot convert a failed implementation into success or erase failure evidence.
  - Keep root and generated runner behavior byte-identical, keep root and generated policy and Skill semantics aligned after path normalization, and preserve supported non-destructive Copier updates.
replan_source: docs/plan/active/114-validate-structured-worker-completion.md
replan_contract: docs/plan/replanned/contracts/114-validate-structured-worker-completion.json
integration_gates:
  - plan 153 must be checked at docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md; tuned scenarios must equal sha256:264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a and the opaque holdout must equal sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76 before implementation starts
  - keep the tuned scenarios read-only and do not inspect or execute the digest-sealed holdout in this plan
  - plan 155 must execute the unchanged holdout only after this implementation is otherwise review-ready
successor_plans:
  - docs/plan/active/153-freeze-worker-completion-receipt-scenarios.md
  - docs/plan/active/154-enforce-structured-worker-completion-receipt.md
  - docs/plan/active/155-integrate-structured-worker-completion-receipt.md
inherited_acceptance_digests:
  - sha256:06c51fc5b5f78aa822c035fccc95b51ce1f72a6f8a53ba7cb3979994c182a252
  - sha256:cc0e91a1c82a44375418b3d4dcfc6e9140da675727149aff02bffed945ce5cea
  - sha256:95ab4926d09833304ba7223b6dfc8ce15fdf4a870566265e03aaf579795b14dd
  - sha256:b29da5035ef6c28f6cb15dd7c9e74e6d0aaea22550eb83d451f147533ca3d089
  - sha256:33683401587ba19a91f7cec022b9a60135cfa8cf6f90b899ef9ad5cd325a4076
  - sha256:ed3224f61d6379b777c481ec2974d3dc706e94efb1506044254a8003e8e5a780
  - sha256:43997ad5fe2020050017d78b835084d1ea3efa60b8f3ddad9d672573e88dcab8
  - sha256:4b360c8a07c7174dbcadaa6e6261828d5ef34f007686bb8f52094529fa3b8daf
  - sha256:b8e2256526a3dcd71afae0f2d9e662e2ffd766c2528c4837bb43654663ee0ba7
  - sha256:00287f9ca9cb9ea1bb9e2ebb4ee5fc1d0badca83daa7d712e3fe48658055ac51
  - sha256:5906dbdbacb32377ea164fff882c5cb1f5b10878410be01b008e50d93015212e
checked_summary_ja: worker完了受領書を試行と候補差分へ結び付けて検証するが、その主張を親の受理判断や検証結果として扱わない。

## Context

The concrete implementation boundary is one active plan that changes the exact root and generated runner files plus aligned root and generated orchestration policy and skill files so each initial or correction attempt emits one bounded completion receipt and the parent validates its schema, identity, lineage, digests, normalized paths, and candidate consistency without transferring lifecycle authority.

## Decisions

- Emit one bounded versioned receipt for every successful or failed initial and correction attempt inside that attempt's output boundary.
- Cross-link receipt identity and candidate facts to the verified worker execution contract, Git-derived changed paths, and emitted candidate patch when present.
- Validate exact schema, bounds, identities, lineage, digests, paths, and candidate consistency before parent diff review; keep every worker claim advisory.
- Preserve process exit status and sanitized diagnostics separately from receipt validity.
- Keep root and generated runner bytes identical and aligned policy and Skill semantics concise.
- Use bounded parent implementation and independent review because runner, tests, and policy are validation authority.

## Tasks

- [ ] Define the receipt schema, size bounds, failure representation, and candidate cross-links from the frozen tuned scenarios.
- [ ] Emit one receipt from initial and correction attempts without giving it lifecycle transition authority.
- [ ] Validate the receipt before parent review and reject malformed, stale, replayed, escaping, deceptive, or inconsistent content without erasing process failure evidence.
- [ ] Align root and generated runner, policy, Skill, checkers, smoke coverage, and Copier preservation without changing frozen fixtures.
- [ ] Review the bounded parent diff, run tuned focused validation, obtain independent review, run the authoritative suite once without the holdout, and archive this plan.

## Validation Notes

- Plan 136 is checked at `docs/plan/checked/2026/08/16-31/136-integrate-plan-bound-worker-contract.md`.
- Plan 153 is a hard predecessor; its fixture files are absent from this write scope.
- The source Plan 114 acceptance text is preserved exactly.
- Plan 153 is checked at `docs/plan/checked/2026/08/16-31/153-freeze-worker-completion-receipt-scenarios.md`.
- The tuned fixture is sealed at `sha256:264462e6276aa4ab6da320e4773b570ac90353a793bb83abccc01993af21793a`; the opaque holdout is sealed at `sha256:4473bf88c87cc99b16b3817d2d57169d2f3a5266ba08ece0758811d7644b3f76` and must not be inspected or executed in this plan.
