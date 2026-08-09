# Add a Luna xhigh evidence synthesis role

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - .codex/agents/
  - docs/plan/
  - references/orchestration.md
  - scripts/
  - template/.codex/agents/
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/docs/plan/sub-agents/
  - tests/
context_files:
  - .agent-artifacts/referent-contracts/luna-xhigh-readonly-comparison/contract.json
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Add evidence_synthesizer to root and generated projects with gpt-5.6-luna and xhigh reasoning in read-only mode.
  - Restrict the role to bounded comparison of multiple evidence sources and keep implementation, final acceptance, and external writes outside the role.
  - Document low, medium, high, xhigh, and max Luna selection boundaries and require a measured or testable reason before selecting high or xhigh.
  - Enforce the new fixed profile after Copier copy and update while preserving unrelated project-owned instructions.
checked_summary_ja: Luna / xhigh の読み取り専用比較役を root と Copier 生成先へ追加し、effort の選択条件と権限境界を固定した。

## Decisions

- Use evidence_synthesizer as the controlled role name defined by the referent-first contract.
- Keep the dedicated role fixed at Luna xhigh rather than overriding routine exploration or documentation roles.
- Do not define a Luna max helper; move hardest final judgment to Terra or Sol unless a separate evaluation proves Luna max useful.

## Tasks

- [x] Add the root and generated evidence_synthesizer definitions.
- [x] Document Luna effort selection and escalation boundaries.
- [x] Extend profile normalization and generated/update validation.
- [x] Run completion validation and archive this plan.

## Validation Notes

- The advisory referent-first contract at `.agent-artifacts/referent-contracts/luna-xhigh-readonly-comparison/contract.json` closed successfully after checking the controlled role definition in `references/orchestration.md`.
- evidence_synthesizer is fixed to gpt-5.6-luna with xhigh reasoning and read-only sandboxing in root and generated agent definitions.
- The role accepts only bounded comparison of multiple evidence sources, alternatives, or hypotheses and excludes edits, external writes, descendant delegation, implementation decisions, final validation acceptance, releases, and final policy judgment.
- `scripts/lint-project-workflow.sh` and `tests/smoke.sh` passed. GitHub Actions lint was skipped inside smoke because actionlint is not installed.
- `COPIER_UPDATE_TARGET_REF=6d284f94740228f0d180d7dea2090ac24b97cbc5 REQUIRE_COPIER=1 tests/copier-update.sh` passed and proved the new role and fixed profile are installed during a v1.1.1 update.
- `tests/copier-minimum.sh`, `python3 scripts/validate-changes.py --all`, and `git diff --check` passed.
