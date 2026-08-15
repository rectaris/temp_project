# Accept npm hard links before private snapshot copying and classify update-created paths

status: checked
primary_invariant: accept npm-created hard links only before runner-owned byte copying, preserve tracked paths with the HEAD inventory, and reject new paths outside the digest-bound current inventory
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
  - tests/test-copier-migration.py
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
  - REQUIRE_NPM=1 python3 tests/test-sandboxed-plan-worker.py
  - REQUIRE_COPIER=1 tests/copier-update.sh
  - python3 scripts/check-copier-template.py
validation:
  - REQUIRE_NPM=1 python3 tests/test-sandboxed-plan-worker.py
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
  - Include git ls-files --others --exclude-standard in post-update ownership inspection, require the updated inventory to match the inventory shipped beside the current validator, and reject additions outside that inventory.
  - Preserve root and generated-template script parity and keep existing rejection of hard links in submitted manifests and runner-private validation copies.
checked_summary_ja: npmが生成するWorkerdのhard linkをrunner所有copyで分離し、Copier更新後の未追跡pathをdigest検証済みの現行ownership inventoryで検査した。

## Decisions

- source_tree_metadata_fingerprint is the SHA-256 value over source entry identity and metadata used only to detect changes across copying.
- Allow multi-link regular files only when reading the source node_modules tree during snapshot preparation.
- Copy source bytes with the existing private-output boundary, then run the strict single-link tree validation and compute the manifest digest only from that copied tree.
- Compare `source_tree_metadata_fingerprint` before and after copying independently from the content digest shared with the copied tree.
- Build the regression fixture with a network-free local npm package whose install script creates the two observed Workerd paths as hard links.
- Keep the committed pre-update inventory for tracked changes, and use the digest-checked current inventory only for non-ignored untracked additions.
- Use bounded parent implementation because this correction changes validation authority and the runner security boundary; require independent read-only review before authoritative validation.

## Tasks

- [x] Add a source-only hard-link allowance and preserve strict validation for copied dependency trees.
- [x] Add an npm ci regression that proves the observed Workerd paths are normalized to separate single-link files.
- [x] Add untracked paths to Copier ownership inspection and test allowed and rejected additions.
- [x] Keep root and template copies synchronized and update deterministic checker requirements if needed.
- [x] Run focused and repository-required validation, then archive the completed plan.

## Validation Notes

- The reported source failure matches the current unconditional `st_nlink != 1` rejection in `digest_tree` reached by `prepare-dependencies` before copying.
- `inspect_project_owned_content` currently reads only `git diff --name-only -z HEAD --` and therefore omits non-ignored untracked additions.
- Focused Copier validation proved that the committed v1.2.1 inventory does not classify legitimate paths introduced by the current template, so the current inventory needs an exact companion-file digest check before it can classify additions.
- `REQUIRE_NPM=1 python3 tests/test-sandboxed-plan-worker.py` passed 73 tests, including an offline `npm ci` fixture that produced the two Workerd paths as one link-count-2 inode and verified separate link-count-1 snapshot files with identical bytes.
- `REQUIRE_COPIER=1 tests/copier-update.sh` passed the supported update fixtures, untracked managed and unclassified additions, broadened inventory rejection, and inventory hard-link, symlink, and read-time mutation rejection.
- `python3 scripts/check-copier-template.py` passed and confirmed root/template parity plus the current inventory digest constant.
- `scripts/lint-project-workflow.sh` and `tests/smoke.sh` passed; Actionlint was unavailable and the existing optional GitHub Actions lint was skipped.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
- The first authoritative run exposed one simplified ownership fixture in `tests/test-copier-migration.py`; replacing it with the exact current template inventory preserved all prior assertions, and the revised authoritative run passed.
- Independent read-only review found two Medium and three Low findings before remediation, then found no remaining High, Medium, or Low finding in two subsequent reviews.

## Evidence Targets

- The regular files at node_modules/@cloudflare/workerd-linux-64/bin/workerd and node_modules/workerd/bin/workerd before snapshot copying.
- Each regular file created under the runner-owned snapshot output node_modules directory.
- The ownership inventory bytes read from HEAD:.project-agent-workflow/ownership.yaml in the destination repository.
- The NUL-delimited paths returned after update by git ls-files --others --exclude-standard.
- The ownership inventory bytes in the updated worktree after their SHA-256 digest matches the inventory shipped beside the current validator.
- A SHA-256 value over every source entry relative path, file type, device, inode, link count, mode, size, modification time, change time, and symbolic-link target.
