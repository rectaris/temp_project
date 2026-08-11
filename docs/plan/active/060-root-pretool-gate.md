# Restore the root PreToolUse hardening gate

status: in_progress
task_types:
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .codex/hooks.json
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - docs/plan/active/060-root-pretool-gate.md
  - scripts/check-copier-template.py
  - tests/test-hooks.py
context_files:
  - docs/agent/SPEC_SECURITY.md
  - template/.codex/hooks.json.jinja
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/scripts/security_rules.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Root `PreToolUse` invokes both the best-effort event logger and a runnable hardening gate.
  - The root gate imports the existing security rules without depending on a removed root managed-scripts directory.
  - Actual nested tool-input payloads reach the hardening rules.
  - Root Hook wiring and runtime behavior have deterministic regression coverage.
checked_summary_ja: ルート PreToolUse に実行可能な hardening gate を再配線し、危険コマンドの決定的な検査を復旧する。

## Context

The root PreToolUse configuration must execute a runnable hardening gate.

The root Hook configuration currently logs PreToolUse but does not invoke the hardening gate, and the root managed gate cannot import `security_rules` when run directly.

## Decisions

- Reuse the generated hardening implementation or its shared security rules instead of copying a second rule set.
- Preserve event logging as a separate best-effort Hook before the blocking gate.

## Tasks

- [ ] Add a runtime regression that executes the root gate path.
- [ ] Repair the root gate's implementation dependency.
- [ ] Add the gate to root `PreToolUse` wiring without removing logging.
- [ ] Add deterministic wiring checks.
- [ ] Run the required validation commands.

## Validation Notes

- Pending.
