# Reuse established decisions through existing planning skills

status: backlog
primary_invariant: Existing planning and execution skills apply one shared decision sequence to the same authorized task without reopening settled choices, inventing successor plans or relaxing normative approval, diagnosis and review boundaries.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"decision-audit already skips mechanical and settled choices; implementation-guidelines prefers reproduce-first fixes; the sequential skill already owns parent acceptance and stopped-run boundaries.","kind":"existing_mechanism"}
  - {"evidence":"Plan 282 checks one authoring input for requirement, path, condition and witness coverage. The Plan 119 record documents root/generated diagnosis confusion.","kind":"existing_mechanism"}
  - {"evidence":"Plan 275 relocates detailed policy only. Operational decision reuse is a separate bounded change following that relocation.","kind":"existing_mechanism"}
completion_conditions:
  - One direct reference contains accepted-decision reuse, requirement/scope/condition/witness preflight and exact-failure reproduction sections, with resolvable conditional links from existing skills.
  - The policy checker loads the fixed scenario fixture and validates required case ids, authorization expectations and policy-reference coverage for unchanged work, changed requirements, safety, external effects, formal diagnosis and stopped budgets.
  - Concise aligned skill bodies treat project policy as normative and add no new skill, state record, evaluation service, numbered investigation or parallel planning authority.
completion_witness_map:
  - {"condition_sha256":"sha256:b6498ea62e278f9f1444cd4c0bbad753154968d8fcc1aeef64f761dfdc502c0a","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:7ac045986249ae2da02438dd0a79b155225a53fa338c0e4b4e4ef3aaed121658","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:ae22add1bf5cd30d0e69cb2eea96f5eed2c7a22c5f4d4944ec70147fc2e3312d","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/decision-audit/SKILL.md
  - .codex/skills/decision-audit/references/implementation-preflight.md
  - template/.project-agent-workflow/skills/decision-audit/SKILL.md
  - template/.project-agent-workflow/skills/decision-audit/references/implementation-preflight.md
  - .codex/skills/implementation-guidelines/SKILL.md
  - template/.project-agent-workflow/skills/implementation-guidelines/SKILL.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/fixtures/agent-policy-routing/scenarios.json
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/plan/backlog/275-route-detailed-agent-policy-on-demand.md
  - docs/plan/checked/2026/09/01-15/282-render-plans-from-checked-authoring-input.md
  - docs/plan/checked/2026/08/16-31/119-integrate-verify-copier-update-skill.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - One direct reference contains accepted-decision reuse, requirement/scope/condition/witness preflight and exact-failure reproduction sections, with resolvable conditional links from existing skills.
  - The policy checker loads the fixed scenario fixture and validates required case ids, authorization expectations and policy-reference coverage for unchanged work, changed requirements, safety, external effects, formal diagnosis and stopped budgets.
  - Concise aligned skill bodies treat project policy as normative and add no new skill, state record, evaluation service, numbered investigation or parallel planning authority.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b6498ea62e278f9f1444cd4c0bbad753154968d8fcc1aeef64f761dfdc502c0a","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:7ac045986249ae2da02438dd0a79b155225a53fa338c0e4b4e4ef3aaed121658","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:ae22add1bf5cd30d0e69cb2eea96f5eed2c7a22c5f4d4944ec70147fc2e3312d","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after this backlog plan is selected for implementation and published as active; use its exact bound task worktree.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - Start after existing Plan 275 is checked. Do not expand 275 itself into skill redesign.
  - Apply system skill-creator guidance during implementation; preserve concise bodies and direct references.
  - Do not change external-service policies, ledger schemas, approval fields, correction budgets, human-report checks or authoring input formats.
checked_summary_ja: 既決事項と失敗の再現確認を既存スキルへまとめ、計画作成と承認要求の重複を減らす。

## Decisions

- After Plan 275, add one direct reference to decision-audit and short conditional links from implementation and sequential skills. Preserve normative policy in existing specifications.
- Identify the requested outcome and accepted decision evidence; distinguish product repair from a request to improve development procedures. Reuse settled choices while requirements, safety and effects remain unchanged.
- Before long plan prose, use the existing authoring check to inspect requirement/path/condition/witness coverage, including counterparts and test-registration files. Require no new form or numbered feasibility plan.
- After formal failure, preserve diagnosis_required and reproduce the exact operation, input, directory and status before proposing repair. This reference grants no independent diagnosis or repair authority.
- A new id, routine checkpoint or skill invocation does not alone require repeated approval. Changed requirements, expanded effects and stopped-run continuation retain existing explicit authorization.
- Use fixed examples and one independent reader evaluation. Routing tests do not prove language understanding or productivity; retain fixed cases when assessing findings.
- Keep the independent reader result as separate semantic evidence for decision reuse and no universal approval gate; the fixture checker proves only its named structural predicates.

## Tasks

- [ ] Record cases for unchanged authorized work, expanded effects, root/generated failure confusion, plan-only requests, absent feasibility and review exhaustion.
- [ ] Create the direct reference and replace duplicated operational explanations with conditional links in existing skills; keep names and trigger scope stable.
- [ ] Align policy and installation inventory without copying the entire lifecycle contract into the skill.
- [ ] Extend check-root-agent-policy.py to load tests/fixtures/agent-policy-routing/scenarios.json and reject missing cases, invalid expectation values and unresolved policy links. These checks establish fixture and routing structure, not agent behavior.
- [ ] Obtain one independent reader review against fixed cases and report observed misinterpretations and unobserved timing separately.
- [ ] Run focused checks and the mandatory suite once for the accepted change.

## Validation Notes

- Planning baseline: b3e300888412f7e9c2fb243435da4cb4082f5135 in temp_project.
- Owner instruction: 提案の方針でプランを作成せよ。変更点が多い場合は複数のプランとして作成せよ。手続きとして削減するべき部分をまとめたり、スキル化、関数化するべき部分など、改善できる部分をまとめよ。
- This instruction authorizes plan authoring, not implementation or reopening a stopped run. This is ordinary backlog work, not a reconstruction successor.
- See docs/plan/backlog/README.md for procedure reductions, existing-plan reuse and implementation order. Full decision audit stays in local development-process-planning evidence.
- The shared authoring checker derives correspondence and digests; the parent reviews witness semantics. No measured productivity saving is claimed.
