# Enforce reader-ready agent communication

status: checked
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
target_files:
  - AGENTS.md
  - docs/agent/
  - .codex/hooks/
  - .codex/skills/
  - template/AGENTS.md.jinja
  - template/docs/agent/
  - template/.codex/hooks/
  - template/.codex/skills/
  - scripts/
  - tests/
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - One normative specification owns user-facing communication requirements in both the root and generated template.
  - AGENTS.md routes every substantive user-facing message to the specification without duplicating its detailed rules.
  - The reusable skill provides an operational drafting workflow without duplicating normative policy.
  - The existing Stop-hook completion gate requests one final communication review when hooks are active.
  - Deterministic tests cover hook activation, bypass behavior, skill parity, routing, and generated output.
expected_output: full-implementation
checked_summary_ja: 利用者が未共有の知識を補わずに理解できる文章規則を、仕様、Skill、終了時検査へ重複なく適用した。

## Problem

Codex can report progress or proposals with unstated assumptions, undefined labels, abstract completion verbs, or unsupported certainty.

The current repository has adjacent Japanese-writing and referent-first policies, but it does not own one general contract for user-facing agent communication or require a final review against that contract.

## Goal

Apply one reader-oriented communication contract to this repository and generated projects, expose a reusable drafting workflow, and integrate a single completion-time review into the existing Stop hook.

## Decisions

- Keep detailed communication requirements only in `docs/agent/SPEC_USER_COMMUNICATION.md` and its template counterpart.
- Keep AGENTS.md as the always-on routing entrypoint and keep the skill as operational workflow guidance.
- Integrate communication review into `stop_review_gate.py` instead of adding another Stop hook.
- Do not duplicate the policy through a UserPromptSubmit hook.
- Respect `codex_hooks_mode: disabled`; policy still applies through generated instructions and the skill when runtime hooks are disabled.
- Use `last_assistant_message` rather than parsing the unstable transcript format.
- Treat deterministic checks as enforcement of a review pass, not proof that every reader will understand the message.

## Implementation Instructions

1. Add aligned root and template communication specifications and route them from agent policy indexes.
2. Add the reusable `write-for-reader` skill and matching UI metadata to root and template.
3. Extend the existing Stop review gate to request one review of substantive user-facing messages against the specification.
4. Extend deterministic repository checks, Hook tests, and Copier smoke coverage without weakening existing validation.
5. Run required validation, review the diff, record evidence, complete the plan, and finalize it.

## Tasks

- [x] Add and route the normative communication specification.
- [x] Add the root and template drafting skill.
- [x] Integrate communication review into the existing Stop gate.
- [x] Add fixed scenarios and deterministic coverage.
- [x] Run validation and archive the completed plan.

## Validation Notes

- `scripts/lint-project-workflow.sh`: passed with 26 Hook tests, 8 referent-contract tests, root/template policy checks, and the root plan lifecycle test.
- `tests/smoke.sh`: passed for primary and pairwise Copier fixtures, generated inventory, plan lifecycle, and the new communication policy and Skill.
- `python3 scripts/validate-changes.py --all`: passed.
- `tests/copier-update.sh`: passed for supported update lanes.
- `tests/copier-minimum.sh`: passed with the declared minimum Copier and Python compatibility lane.
- `quick_validate.py` passed for the root and template `write-for-reader` Skill directories.
- `git diff --check`: passed.
- The advisory referent contract closed after its controlled term and target draft passed structural validation.
- Independent semantic evaluation remains pending because this turn did not authorize subagents or parallel evaluator sessions.
- Remaining runtime boundary: the Stop-hook review runs only when Codex hooks are enabled; `codex_hooks_mode: disabled` still applies the policy and Skill instructions without the runtime completion gate.
