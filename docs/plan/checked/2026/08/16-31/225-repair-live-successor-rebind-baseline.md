# Repair the live successor rebind baseline lineage

status: checked
implementation_tier: 2
primary_invariant: repository lineage verification succeeds only when every live contract successor's reservation and protected manifest fields are reproduced by the recorded rebind, activation, or owner-authorized reservation record sequence
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: high
write_scope:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/plan/active/185-complete-bounded-copier-fixture-runtime.md
  - docs/plan/replanned/baselines/live-successor-rebinds-v1.json
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - git diff --check
validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/restructure-plan.py --verify
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Bind every owner-authorized reservation-field change to one durable rebind-baseline record that names its authorizing commit, and keep write_scope and preservation_scope otherwise immutable against rebind and activation records.
  - Record the missing Plan 185 activation, drop its unsanctioned context promotion, and make repository lineage verification succeed on a clean worktree without editing any checked archive.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b0c9372582e426549a02f38802140292c88bb6576ad584636f5c79644602b17b","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:35f2edb9d54dda9a8efab46fd7e2dc8cb2cdd244c95389520edc0949427edf69","stage":"focused","witness":"python3 scripts/restructure-plan.py --verify"}
integration_gates:
  - do not edit any file under docs/plan/checked/; the checked Plan 205 archive stays byte-identical
  - Plan 185 restructuring may start only after this plan is checked and repository lineage verification succeeds
checked_summary_ja: 記録されていないreservation変更とactivationをbaselineへ正規に記録し、lineage検証を回復する。

## Decisions

- Repository lineage verification currently fails on a clean worktree at HEAD for two live contract successors, so every `scripts/restructure-plan.py` operation, including `--verify` and the schema-3 `rebind` operation, refuses to run. This blocks the Plan 185 restructuring, and the user authorized repairing the lineage as an independent plan before that restructuring resumes.
- Defect A is `docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md`. Commit `5d05ab5` added `tests/copier-update.sh` to its `write_scope` as an owner-authorized extension, but `docs/agent/SPEC_PLAN_WORKFLOW.md` treats both reservation fields as rebind-protected and offers no record that can carry the change, so the recorded activation record no longer reproduces the live bytes.
- Defect B is `docs/plan/active/185-complete-bounded-copier-fixture-runtime.md`. Commit `661de44` performed its activation by direct edit without appending an `activation` record, and additionally added `scripts/project_workflow/copier_fixture_validator.py` to `context_files` although that path was never in `preservation_scope` and therefore never qualified for the sanctioned promotion.
- Repair Defect A by adding one durable reservation record to the rebind baseline instead of rewriting the checked archive. The authorized extension is real project history, and reverting the archived plan text would falsify what the owner approved. The new record binds the plan path, the exact field, the exact added or removed entries, the authorizing commit, the prior and resulting content digests, and its own record digest, and lineage verification re-authorizes it like every other durable record.
- Keep reservation fields immutable against `rebind` and `activation` records. Only the new reservation record may change them, and only when the named authorizing commit is an ancestor of HEAD and its diff contains exactly that field change for that plan.
- Repair Defect B by removing the unsanctioned `context_files` entry from Plan 185 and appending one `activation` record covering its status, deferred reason, and predecessor rebinding. Plan 185 is stopped and will be archived by its own restructuring, so the removed context entry grants nothing and no requirement is lost.
- Mirror both the policy text and the tool into `template/` in the same change, because root and template must stay in the same state.
- Use bounded parent implementation with independent review. Both `implementation_risk` and `implementation_ambiguity` are high, so the writable sandboxed runner is refused.

## Tasks

- [x] Reproduce both verification failures on a clean worktree and record the exact failing paths, fields, and authorizing commits.
- [x] Extend `docs/agent/SPEC_PLAN_WORKFLOW.md` with the reservation record, its authorizing-commit binding, and the unchanged immutability of reservation fields against rebind and activation records.
- [x] Implement the reservation record kind, its validation, and its re-authorization during repository verification in `scripts/restructure-plan.py`.
- [x] Extend `tests/test-plan-restructure.py` with positive and mutation coverage for the reservation record, including a forged authorizing commit, a commit that changes a different field, and a commit that is not an ancestor of HEAD.
- [x] Append the Plan 205 reservation record and the Plan 185 activation record, and remove the unsanctioned Plan 185 context entry.
- [x] Mirror the policy and tool changes into `template/` and confirm the alignment checks pass.
- [x] Complete independent review with zero unresolved High or Medium findings, then run the authoritative validation suite once.

## Validation Notes

- Verification at HEAD `85c0f0f` reports `rebind baseline final projection: docs/plan/active/185-complete-bounded-copier-fixture-runtime.md changes protected manifest field: context_files` and `rebind baseline final projection: docs/plan/active/205-integrate-bounded-copier-fixture-validator.md changes protected manifest field: write_scope`.
- Both defects predate this plan and were introduced by commits `5d05ab5` and `661de44`.
- Do not run `tests/copier-update.sh`; Plan 179 retains the sole complete transition execution.
- Implemented the `reservation` record kind, the dedicated schema-3 `reserve` operation, and a transaction-scoped `pending_reservations` exemption that compares the live file against the authorizing commit's own bytes for exactly the reserved plan paths, which is what lets the repairing record be recorded while verification still fails.
- Appended one `reservation` record for `docs/plan/active/205-integrate-bounded-copier-fixture-validator.md` bound to authorizing commit `5d05ab5db99c239854dab9bb43827cb31847769f`, and one `activation` record for `docs/plan/active/185-complete-bounded-copier-fixture-runtime.md`, and removed the unsanctioned Plan 185 context entry. No file under `docs/plan/checked/` was edited.
- Independent review of the complete candidate diff reported zero High and zero Medium findings.
- Authoritative validation passed once: `python3 tests/test-plan-restructure.py` (145 tests), `python3 scripts/restructure-plan.py --verify` (`replanned contracts verified`), `scripts/lint-project-workflow.sh`, `tests/smoke.sh`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
