# Check tool and system assumptions before implementation and improve the existing development guidance from observed failures

status: backlog
primary_invariant: Existing development guidance connects design-critical assumptions to evidence and reusable corrective action without inventing authority, reopening stopped work, or presenting structural checks as proof of agent behavior.
task_types:
  - template_workflow
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At ad6b904, SPEC_DECISION_AUDIT and the shared implementation-preflight reference already route accepted decisions, authoring correspondence and failure reproduction. Existing skills can carry the proposed sequence without another skill or authoring format.","kind":"existing_mechanism"}
  - {"evidence":"check_decision_reuse_scenarios, require_decision_reuse_alignment and PlanValidationCommandsTest already exercise checker-owned scenario expectations, operative routing, mutations and root/template alignment. Their checks explicitly do not prove agent behavior.","kind":"existing_mechanism"}
  - {"evidence":"SPEC_TEMPLATE_FEEDBACK already records expected and observed behavior, evidence, desired behavior and unresolved attribution. The existing agent-policy-routing evaluation protocol separates fixed cases from an independently sealed, untuned holdout.","kind":"existing_mechanism"}
  - {"evidence":"The stopped 364 candidate filtered RUFF_* but still accepted an anonymous replacement ruff package through PYTHONPATH: both wrappers returned zero without running installed Ruff. This is bounded evidence of an untested execution assumption, not proof of a generic template defect.","kind":"reproduced_defect"}
completion_conditions:
  - Routed guidance connects existing processing and ownership, version-specific tool behavior, and intended end-to-end behavior to the evidence for each design-critical assumption, while retaining mechanical-task exclusions and justified reuse of accepted decisions.
  - Guidance calls for bounded normal and assumption-breaking probes before broad integration when material uncertainty remains, distinguishes documentation claims from observations, and keeps unresolved assumptions explicit without creating numbered investigation plans.
  - Guidance distinguishes code that violates a settled design from evidence that invalidates a design assumption; the latter returns to decision audit before another patch while preserving existing diagnosis, review-budget and owner-authorization rules.
  - Existing feedback guidance records the failed assumption, counterexample and next earlier check using the current schema; it distinguishes operating omissions, policy gaps and regressions, preserving unknown attribution and separate task-bound persistence.
  - Registered scenarios cover tool/environment mismatch, incomplete system ownership, invalidated assumptions, unchanged simple work and stopped-run continuation; mutation tests refuse missing coverage or weakened expectations without replacing semantic judgment.
  - The existing evaluation protocol specifies matched baseline/candidate inputs, fixed criteria, independently sealed holdout handling, critical-failure stops and reporting of observed effects and added effort without claiming productivity from static checks.
  - Root and generated instructions remain aligned within existing skill size limits and retain existing authority and routing; the change adds no skill, dependency, authoring schema, execution ledger, review allowance or automatic improvement-publication path.
  - The existing all-change selector executes the required skill-change checks after the guidance changes without replacing the separately declared authoritative suite or treating those checks as independent semantic evaluation.
completion_witness_map:
  - {"condition_sha256":"sha256:c5aeb185567508279525dbaf3a984e5208a5d10fa8a02cf6599f636d8b4cb77c","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:6eea1171ef907c724621ab0403247af7290a57268234ee971cc35ba5a9d4e89b","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:ba12bd50ec09948829f4fa376ab14e4a6e1655f0518cbe2f7cc33e51430e7ce4","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:e3695e8cf00d307c10cad1635db90596f925d12216f7b069f58bd1d8a4da5983","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:a2d05fc61d214cd16dd15d8ce791b52d0c97af8d4a6d650ea83130d64ab1174e","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a0fb52a35ad125de209a0ca3b75ac256b4947989e182167f666cd775b65b9681","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:60c7d783331297763ef8905b42ee9a73b918763ee410125d2a5b7515aa642fb3","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:0e8d6ccca99a707d507262bc6bfddaae6c710138cb4e480a0062b9ad99fc42b9","witness":"python3 scripts/validate-changes.py --all"}
write_scope:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md
  - .codex/skills/decision-audit/references/implementation-preflight.md
  - template/.project-agent-workflow/skills/decision-audit/references/implementation-preflight.md
  - .codex/skills/implementation-guidelines/SKILL.md
  - template/.project-agent-workflow/skills/implementation-guidelines/SKILL.md
  - docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - template/.project-agent-workflow/docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/validation_tools/plan.py
  - tests/fixtures/agent-policy-routing/scenarios.json
  - tests/fixtures/agent-policy-routing/evaluation-protocol.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/template-feedback.json
  - docs/plan/checked/2026/09/01-15/299-reuse-established-decisions-in-existing-skills.md
  - docs/plan/replanned/2026/09/16-31/364-enforce-bounded-python-lint.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/validate-changes.py --all
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Contributors receive aligned, bounded guidance and evaluation resources that connect tool behavior, current-system constraints and intended behavior before implementation, and turn observed failures into reusable improvements without weakening existing authority or overstating the evidence.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:42a9b7257e5e46e62bba8fae1ffe635afa12c167aeb5424a235a3e79a92d876b","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
checked_summary_ja: ツールの挙動とシステムの制約を実装前に照合し、見落としから既存の開発手順を改善する。

## Decisions

- The owner accepted the proposed development approach and requested its implementation plan on 2026-09-16. Author this plan in backlog; creating it is not implementing it. Plan 364 is a motivating context, not a prerequisite that must complete before this independent guidance work can be selected.
- Use parent-direct implementation after ordinary active-plan publication because the scope changes normative guidance and validation code. The request to continue 364 is separate; this plan never reopens its stopped runs, changes its candidate or refreshes its review allowance.
- Extend the existing decision-audit reference rather than create a form, skill, state store or universal new gate. Keep accepted-decision reuse, the existing authority denials and the current plain-prose and byte-size constraints.
- Before broad implementation, connect the current call flow, ownership and retained behavior with the adopted tool version's documented and observed configuration, input/output, lookup, environment, side effects and failure behavior. Choose only uncertainties that could invalidate the requested behavior.
- For those uncertainties, choose bounded probes with a normal case and an assumption-breaking case. Record actual observations and limitations rather than treating a version string, successful exit or aggregate check count as proof of the required property.
- Return to design judgment when evidence invalidates an assumption. Do not turn every implementation mistake into a redesign, or confuse read-only investigation with permission to continue a stopped run. Preserve the existing formal-failure diagnosis sequence.
- Use the existing feedback fields for the assumption, counterexample, impact and earlier future check. Distinguish execution omissions, insufficient guidance and deterministic defects before choosing an operational, policy or regression-test improvement; retain unknown attribution and current persistence rules.
- Reuse PlanValidationCommandsTest and the existing fixed scenario fixture. Keep required expectations in checker-owned code rather than let fixtures redefine correctness. Extend structural checks only for explicit predicates; do not build another approximate Markdown parser or claim static checks prove reasoning quality.
- Extend the existing evaluation protocol, preserving its independent sealed holdout boundary. Compare frozen baseline and candidate instructions with the same fixed task inputs and criteria, record evaluator identity and actual observations, and keep raw outputs local. Do not expose or tune on the holdout.
- Obtain independent semantic evaluation of the final guidance as required by the existing protocol. Include unchanged small work, tool lookup and output effects, existing ownership constraints, a review that invalidates an assumption, feedback with unknown attribution, and exhausted execution authority. Any critical authority or ignored-stop failure remains stopped under current policy.
- Use the same permitted evaluator route for baseline and candidate, bound model and instruction revisions, and report confounders or unavailable measurements. Report no demonstrated improvement when comparison does not show one; no productivity or universal future-reliability claim is an acceptance shortcut.
- Keep generic instructions free of plan-364-specific settings. Put concrete synthetic cases in the root-only test fixture. Preserve skill names, trigger scope and UI purpose; keep detailed guidance in the existing direct reference.
- Run the declared skill-change selection as focused validation and the unchanged authoritative suite exactly once for an otherwise acceptable candidate. Guidance evaluation is not a substitute for the implementation's formal review, and neither evaluation creates a review allowance for another plan.

## Tasks

- [ ] Translate the accepted approach into bounded additions to the paired decision-audit policy and direct preflight reference, naming the evidence needed for material tool/system assumptions and retaining the existing exclusions.
- [ ] Route unexpected assumption failures from the existing implementation guidelines back to normative decision audit without changing the current execution or repair permissions.
- [ ] Extend paired template-feedback guidance using its current fields and modes; document how operating omissions, policy gaps and reproducible defects lead to different corrective actions.
- [ ] Extend the existing fixed scenarios and checker-owned structural expectations for the new guidance, including negative cases for redundant work and attempts to treat a procedure improvement as stopped-run authority.
- [ ] Add missing-instruction, weakened-expectation and counterpart-drift mutations to PlanValidationCommandsTest without changing aggregate registration or weakening current routing checks.
- [ ] Extend the existing evaluation protocol; arrange its independently sealed holdout before freezing the candidate and retain baseline/candidate observations and evidence identities locally.
- [ ] Evaluate the frozen root and generated instructions against the fixed cases and the untuned holdout, record misinterpretations and unobserved outcomes honestly, and stop on critical failures through existing rules.
- [ ] Review the exact in-scope change, run focused skill checks and the authoritative suite, commit only the accepted guidance change, and complete the ordinary lifecycle and task publication.

## Validation Notes

- Planning source: ad6b90471ae33ab334a9f79ff8011be693792129 in temp_project. Existing policy, skills, checker code, scenario protocol and the checked 299 record were read directly; the historical continuation behavior in 299 does not authorize continuation under current rules.
- Owner instruction: 提案の方針のプランを作成せよ。その後 364 の追加修正と開発を継続せよ。
- Plan 364's terminal review still has one reproduced Medium finding. Current policy permits no later terminal continuation, including under a new owner quotation. This authoring work preserves its plan, candidate, stopped ledgers and registries.
- The focused witness claims are structural and regression claims, not assertions that current checks already prove the proposed behavior. The independent evaluation required during implementation supplies separate semantic observations.
- No improvement in elapsed time, review count or future reliability has yet been measured. Record an unchanged or inconclusive comparison honestly instead of claiming this plan proves all future agents will follow the guidance.
