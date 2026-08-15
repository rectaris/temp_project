# Add bounded writable Vite caches to isolated npm validation

status: in_progress
primary_invariant: run npm validation with the declared project Node runtime and a read-only verified dependency tree while giving each command only disposable Vite caches
task_types:
  - planning_docs
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - docs/plan/
  - references/orchestration.md
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/088-copier-update-safety-contract.md
  - docs/plan/checked/2026/08/01-15/089-copier-wrapper-self-update.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Keep the verified node_modules snapshot mounted read-only and keep validation network-disabled.
  - Require a project `.node-version`, use only a host Node/npm runtime whose major version matches it, mount that exact runtime root read-only, and record bounded runtime version and executable digests.
  - Give each validation command fresh writable scratch mounts only at node_modules/.vite and node_modules/.vite-temp.
  - Support snapshots whether those two cache directories were present or absent without changing the verified snapshot or its recorded digest.
  - Prove that Vite-style cache writes succeed while package-file writes fail and source, snapshot, and private dependency bytes remain unchanged.
  - Keep root and generated runners byte-identical and document the bounded cache exception.
  - Finish with zero unresolved High or Medium independent-review findings.
checked_summary_ja: 隔離npm検証で依存本体を読取専用に保ち、コマンド別のViteキャッシュだけを書込可能にした。

## Decisions

- Mount the verified dependency tree read-only before mounting the two nested writable cache shadows.
- Treat the `.node-version`-matched host Node/npm installation as a parent-approved read-only toolchain input, separate from the lock-bound dependency snapshot and otherwise-hidden host home.
- Create missing cache mountpoint directories only in the parent-private dependency copy, remove them before each digest comparison, and never modify the external snapshot.
- Allocate cache contents below each validation command's scratch directory so commands cannot share cache state.

## Tasks

- [ ] Add failing coverage for Vite cache writes against a read-only dependency snapshot.
- [ ] Add the two command-local writable cache overlays and preserve dependency digest checks.
- [ ] Keep generated policy and runner parity aligned.
- [ ] Run focused validation, independent review, authoritative validation, archive, and commit.

## Validation Notes

- A real `npm run verify` in gakumasu-timeline reached Vitest through the verified snapshot and failed with `EROFS` while opening `node_modules/.vite-temp/vitest.config.js.timestamp-*.mjs`.
