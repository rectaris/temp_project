# State the no-push rule in the root and generated security policy

status: checked
primary_invariant: A reader who follows the security policy alone learns that pushing requires an explicit user request.
task_types:
  - documentation_policy_alignment
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
implementation_mode: parent_direct
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Neither docs/agent/SPEC_SECURITY.md nor template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md contains the substring push, so an agent that reads only the security policy finds no statement of the rule.","kind":"reproduced_defect"}
  - {"evidence":"scripts/check-copier-template.py already enforces semantic alignment between the root and template copies of the security policy, so a mirrored edit is checked by an existing command.","kind":"existing_mechanism"}
completion_conditions:
  - docs/agent/SPEC_SECURITY.md states that a push happens only on an explicit user request, and the root agent policy checker accepts the file.
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md carries the same rule for a generated project and the copier template check accepts the pair.
completion_witness_map:
  - {"condition_sha256":"sha256:0f4efc16a32dddb4daa50258dc36156c11a5ea4a9f434708251f00c900e4aa39","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:7038ff8edccb6b502decc0408afb8c3738d175fdb7eb93a2b020f61fd8465511","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/validation.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The no-push rule is readable from the security policy alone, in both the root and generated copies, without consulting AGENTS.md.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a2a41f38271bdb48130b13e471d9a9358136474d3d980499e09fe7539720c771","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
checked_summary_ja: ルートと生成物のセキュリティ方針に push 禁止規則を明記する

## Decisions

- Use bounded parent implementation for the two security-policy files, with independent read-only review and unchanged validation and external-effect authority.
- State the rule in the security policy and keep the existing AGENTS.md sentence; the two are not in conflict and removing either would lose a routing path.
- Add no new checker. The existing root policy check and copier template check already cover both files.

## Tasks

- [x] Add the no-push rule to docs/agent/SPEC_SECURITY.md in the section that governs remote and repository effects.
- [x] Mirror the same rule into template/.project-agent-workflow/docs/agent/SPEC_SECURITY.md.
- [x] Run the focused checks and then the authoritative suite once.

## Validation Notes

- The owner's 2026-09-09 instruction to implement every backlog plan authorizes this activation. Replace the nonexistent root SPEC_VALIDATION.md reference with the existing root validation policy, references/validation.md; validation commands and acceptance remain unchanged.
- Both policies now state "Do not push unless the user explicitly requests it." The existing AGENTS.md rule remains intact, with no profile exception.
- Independent read-only Sol review reported no High or Medium findings. The parent inspected and accepted the exact mirrored diff.
- Focused validation passed: python3 scripts/check-root-agent-policy.py and python3 scripts/check-copier-template.py.
- Authoritative validation passed once: scripts/lint-project-workflow.sh and tests/smoke.sh. Optional actionlint was unavailable and skipped by the existing smoke command.
- Product commit: af1628d. No remote push was performed.
