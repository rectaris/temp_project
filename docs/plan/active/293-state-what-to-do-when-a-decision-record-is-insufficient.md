# Say how to proceed when an accepted-decision record cannot establish a reuse condition

status: in_progress
primary_invariant: A reader who cannot establish one reuse condition from a decision record is told exactly what to do next, rather than being left to choose.
task_types:
  - documentation_policy_alignment
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: ordinary
implementation_mode: parent_direct
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The accepted-decision section of references/implementation-preflight.md requires four conditions to hold before a recorded decision may be reused, but states no action for the case where the record is silent or ambiguous about one of them, so a reader must invent a rule.","kind":"reproduced_defect"}
  - {"evidence":"scripts/check-root-agent-policy.py already loads the shared reference and validates checker-owned expectations about its sections, so a new required phrase is enforced by an existing command.","kind":"existing_mechanism"}
completion_conditions:
  - .codex/skills/decision-audit/references/implementation-preflight.md states the required action when a decision record cannot establish one of the four reuse conditions, and the root agent policy checker enforces that the statement is present.
  - The generated reference carries the same statement and the copier template check accepts the aligned pair.
completion_witness_map:
  - {"condition_sha256":"sha256:2cda9963d9caf4e599501e873e847523606003f2aa2516dbe0a93d511084173d","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:3795396b9d9922957c4ef8993de1db74be33197836c3d0078a64fb7980f710df","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/decision-audit/references/implementation-preflight.md
  - template/.project-agent-workflow/skills/decision-audit/references/implementation-preflight.md
  - scripts/check-root-agent-policy.py
preservation_scope:
  - none
context_files:
  - docs/agent/SPEC_DECISION_AUDIT.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/validation.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A record that cannot establish one of the four reuse conditions leads to a single stated action rather than reader judgement, in both the root and generated copies.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:2f42ca027c4e18d895155c600b8882870596a2d14f00cea1d79f1e52f5d1d3a8","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
checked_summary_ja: 決定記録が再利用条件を満たせないときの進め方を明記する

## Decisions

- Use bounded parent implementation and independent read-only review because the exact write scope includes validation authority. Classify the checker edit as Tier 2; preserve the acceptance and all declared validation commands.
- Treat an insufficient record as a decision that has not been made, so the reader runs the decision audit instead of reusing the record. Do not add a partial-reuse path.
- Pin the new statement with an expectation in the existing checker rather than adding a new check.

## Tasks

- [ ] State in the accepted-decision section that a record which cannot establish one of the four conditions is not reusable, and name the decision audit as the required next step.
- [ ] Mirror the statement into the generated reference.
- [ ] Add the checker expectation to scripts/check-root-agent-policy.py.
- [ ] Run the focused checks and then the authoritative suite once.

## Validation Notes

- The owner's 2026-09-09 instruction to implement every backlog plan authorizes this activation. Replace the nonexistent root SPEC_VALIDATION.md reference with references/validation.md and add the applicable decision-audit and skill-authoring policies.
