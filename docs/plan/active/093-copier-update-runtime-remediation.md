# Accept npm hard links before private snapshot copying and classify update-created paths

status: active
primary_invariant: accept npm-created hard links only before runner-owned byte copying, and reject every Copier-created path outside the committed ownership inventory
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/test-sandboxed-plan-worker.py
  - tests/copier-update.sh
  - scripts/check-copier-template.py
  - docs/plan/
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/088-copier-update-safety-contract.md
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/check-copier-template.py
validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Permit single-inode regular files in the source node_modules tree only while copying them into a newly created runner-owned dependency snapshot.
  - Require every regular file in the copied dependency snapshot to have one link before validation, digest creation, later private copying, or read-only binding.
  - Detect source-tree content or metadata changes across copying without mounting or executing the source node_modules tree.
  - Reproduce npm ci output with the Workerd paths node_modules/@cloudflare/workerd-linux-64/bin/workerd and node_modules/workerd/bin/workerd sharing an inode, then prove snapshot preparation creates separate single-link files with unchanged bytes.
  - Include git ls-files --others --exclude-standard in post-update ownership inspection and reject update-created paths not allowed by the committed pre-update ownership inventory.
  - Preserve root and generated-template script parity and keep existing rejection of hard links in submitted manifests and runner-private validation copies.
checked_summary_ja: npmが生成するWorkerdのhard linkをrunner所有copyで分離し、Copier更新後の未追跡pathも旧ownership inventoryで検査した。

## Decisions

- Allow multi-link regular files only when reading the source node_modules tree during snapshot preparation.
- Copy source bytes with the existing private-output boundary, then run the strict single-link tree validation and compute the manifest digest only from that copied tree.
- Build the regression fixture with a network-free local npm package whose install script creates the two observed Workerd paths as hard links.
- Union tracked changes and non-ignored untracked paths before applying the committed ownership inventory; do not broaden any ownership pattern.
- Use bounded parent implementation because this correction changes validation authority and the runner security boundary; require independent read-only review before authoritative validation.

## Tasks

- [ ] Add a source-only hard-link allowance and preserve strict validation for copied dependency trees.
- [ ] Add an npm ci regression that proves the observed Workerd paths are normalized to separate single-link files.
- [ ] Add untracked paths to Copier ownership inspection and test allowed and rejected additions.
- [ ] Keep root and template copies synchronized and update deterministic checker requirements if needed.
- [ ] Run focused and repository-required validation, then archive the completed plan.

## Validation Notes

- The reported source failure matches the current unconditional `st_nlink != 1` rejection in `digest_tree` reached by `prepare-dependencies` before copying.
- `inspect_project_owned_content` currently reads only `git diff --name-only -z HEAD --` and therefore omits non-ignored untracked additions.

## Evidence Targets

- The regular files at node_modules/@cloudflare/workerd-linux-64/bin/workerd and node_modules/workerd/bin/workerd before snapshot copying.
- Each regular file created under the runner-owned snapshot output node_modules directory.
- The ownership inventory bytes read from HEAD:.project-agent-workflow/ownership.yaml in the destination repository.
- The NUL-delimited paths returned after update by git ls-files --others --exclude-standard.
