# Make pre-label referent staging visible in chat

status: ready_to_archive
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - AGENTS.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - .codex/skills/define-referents-first/SKILL.md
  - template/AGENTS.md.jinja
  - template/docs/agent/SPEC_REFERENT_FIRST.md
  - template/.codex/skills/define-referents-first/SKILL.md
  - tests/test-referent-contract.py
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 /home/rectaris/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/define-referents-first
  - python3 /home/rectaris/.codex/skills/.system/skill-creator/scripts/quick_validate.py template/.codex/skills/define-referents-first
  - git diff --check
acceptance:
  - Chat naming work visibly lists unnamed concrete referents, kinds, boundaries, and uncertainty before assigning controlled terms.
  - Chat output does not claim that a file contract is required or emit a default artifact-order disclaimer.
  - Assigned labels and first-use definitions preserve the semantic kind fixed in the unnamed referent stage.
  - File-based contract validation and the distinction from hidden model reasoning remain unchanged.
  - Root and generated-template instructions remain semantically aligned.
  - Fresh-context evaluation passes all current-arm critical requirements without a negative-case false trigger.
  - A supplemental blind hold-out fixed before the uncertainty-scope change passes all critical requirements.
expected_output: scoped-policy-fix
checked_summary_ja: チャットで無名の指示対象を先に示し、意味種別、不確実性、原文の具体性、手順順序を保ってから名称を割り当てる規則を追加した。

## Problem

Independent judges agreed that the current implicit-policy artifact assigned controlled terms in the same bullets that first described the referents.

The explicit-skill artifact passed because it displayed unnamed referents before the naming section.

Forward tests then exposed four additional boundaries: unresolved derivation was merged into a settled value, naming changed an event into a time point, a threshold predicate was classified as a transition event, and executable summaries added workflow steps absent from the source.

## Decisions

- Require a visible unnamed-referent stage before controlled terms in chat naming work.
- Treat visible chat ordering as an output requirement without claiming it proves hidden model reasoning order.
- Do not require a default artifact-order disclaimer in user-facing chat output.
- Attach uncertainty to the narrowest unresolved property or rule without merging it into an otherwise settled referent.
- Reject labels or definitions that change a sealed referent's semantic kind.
- Classify semantic kind from source role, including threshold predicates as conditions and established crossing occurrences as events.
- Preserve source specificity instead of inventing operators, inclusivity, units, causality, timing, or derivation rules.
- Keep executable summaries limited to source-stated actions and branches; leave unstated next actions unresolved.
- Keep root and generated-template policy, entrypoint, and skill wording aligned.
- Use deterministic checks for distribution and fresh-context evaluation for semantic behavior.

## Tasks

- [x] Update root and template entrypoint, policy, and skill wording.
- [x] Add deterministic root and generated-template assertions for the chat two-stage rule.
- [x] Run repository and skill validation.
- [x] Rerun fixed scenarios with fresh-context generators and independent judges.
- [x] Archive the completed plan and commit the scoped change.

## Validation Notes

- Initial empirical run: baseline 9/11 or 10/11 critical passes, implicit 10/11, explicit 11/11 across two independent judges.
- Both judges failed the implicit median artifact on visible pre-label sealing.
- Supplemental blind hold-out was fixed before the uncertainty-scope wording changed: SHA-256 `0c23746fa8d89789fe073df3f1720e953947773bb6758d05e5ed8f667db545bc`.
- Final pre-kind-check run preserved visible ordering but changed a sealed event into a time-point label; both independent judges rejected it at 10/11 critical passes.
- Two final median generations and one retry regression generation passed 9/9 critical and 12/12 total requirements under both independent judges.
- The supplemental blind hold-out passed every critical requirement under an independent judge.
- Final-state edge and negative generations passed 5/5 critical and 6/6 total requirements under both independent judges, with zero false triggers.
- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed, including 15 hook tests and 8 referent-contract tests.
- `tests/smoke.sh` passed for generated Copier fixtures and the generated referent-contract lifecycle.
- Skill Creator `quick_validate.py` passed for root and template `define-referents-first` skills.
- `git diff --check` passed.
- Final primary fixed-scenario set passed 11/11 critical and 14/14 total requirements across 4/4 scenarios, with zero negative false triggers.
- Three final median generations and two final edge generations passed independent requirement and source-fidelity review.
- The latest supplemental blind hold-out passed 4/4 critical requirements without referent, kind, or label collisions or unsupported certainty.
- Local evaluation evidence: `.agent-artifacts/referent-evaluation-20260721/manifest.md`.
- Local evidence manifest: `.agent-artifacts/referent-evaluation-20260721/manifest.md`.
