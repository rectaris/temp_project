# Remediate template review findings

status: ready_to_archive
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - copier.yml
  - docs/agent/
  - template/.codex/
  - template/.github/
  - template/docs/agent/
  - template/scripts/
  - scripts/
  - tests/
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_CONTEXT_COMPRESSION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
  - git diff --check
acceptance:
  - Generated logging, compression, hook, and completion lifecycle components share one tested contract.
  - Copier input, generated policy routing, and generated configuration fail safely across supported answers.
  - Plan routing and Class C approval states are executable and linted consistently.
  - Generated CI and CI autofix use safe defaults and deterministic workflow-integrity checks.
  - Template ownership, security policy, model defaults, and Japanese prose boundaries are explicit.
  - Fresh-render and update tests cover semantic parsing, routed paths, conditional outputs, and managed-file preservation.
expected_output: full-implementation
checked_summary_ja: テンプレートレビューで確認した生成、ログ、計画、CI、検証の不整合を修正する。

## Problem

The template passes its current lint and smoke checks while generated projects can still contain invalid routing YAML, incompatible log manifests, disconnected hooks, ambiguous plan routing, unsafe CI defaults, and update-sensitive ownership boundaries.

## Goal

Make the generated workflow safe by default and prove its cross-file contracts through deterministic fresh-render and update validation.

## Decisions

- Default CI autofix to patch-only and require explicit Copier opt-in for direct push.
- Use one Python manifest implementation for hook logs, transcript imports, and compressed outputs.
- Allowlist persisted hook payload fields and mark automatic redaction as pending review unless reviewed evidence establishes otherwise.
- Wire the hardening gate only when generated hooks are enabled and keep installed-only hook templates inactive.
- Make plan task types resolve directly to spec-index route keys.
- Allow Class C approval-pending plans only before active implementation and require approval at the implementation boundary.
- Keep Copier-managed generic specs separate from project-owned extension specs.
- Validate slugs strictly and escape human text at each generated YAML boundary.
- Fail generated CI when configured validation tools are unavailable and always run workflow-integrity checks.
- Do not pin the generated project-wide Codex model or entitlement-specific worker models.
- Add a concrete routed security policy.
- Replace existence-only coverage with generated syntax, route, manifest, hook, and update contract tests.

## Implementation Instructions

1. Add failing focused tests for manifest compatibility, hook wiring, completion plan-only behavior, Copier YAML escaping, routing, Class C approval, CI defaults, and generated configuration.
2. Introduce the shared logging manifest helper and align compression, hook logging, transcript import, validators, and documentation.
3. Align enabled hook wiring and completion lifecycle behavior while preserving disabled and installed-only modes.
4. Align plan task types, approval states, generated plan defaults, and routed required specs.
5. Harden Copier inputs and separate generic managed specs from project-owned extension files.
6. Add the routed security policy, safe CI/autofix defaults, and model configuration defaults.
7. Strengthen fresh-render and update semantic validation, then align Japanese prose and human-facing links.
8. Run the complete validation matrix, review the diff, record validation notes, and archive the plan.

## Tasks

- [x] Add regression tests for every accepted decision.
- [x] Repair logging, compression, hook, and completion contracts.
- [x] Repair plan routing and approval lifecycle contracts.
- [x] Repair Copier input and managed-file ownership contracts.
- [x] Harden generated CI, autofix, security routing, and model defaults.
- [x] Strengthen fresh-render and update semantic validation.
- [x] Align generated documentation and complete validation.

## Validation Notes

- `python3 scripts/validate-changes.py --all`: passed.
- `scripts/lint-project-workflow.sh`: passed, including 16 hook tests and 8 referent-contract tests.
- `tests/smoke.sh`: passed across the TypeScript, Python, docs, and escaping fixtures.
- `tests/copier-update.sh`: passed from the `v0.4.1` update baseline and preserved project-owned policy files.
- `git diff --check`: passed.
- Remaining risk: GitHub Actions syntax and mode-specific content were rendered and inspected locally, but the hosted Codex action and branch-push path were not executed against a live pull request.
- Deferred work: none.
