# Complete safe shared-report supersedes

status: checked
primary_invariant: An explicit shared-report supersede validates the existing stored pair before any write, preserves both verified files byte-for-byte when publication content is unchanged, and can replace stale provenance with a current deterministic pair when any non-time field changes.
replan_sources:
  - docs/plan/active/254-preserve-identical-human-report-supersede.md
replan_contract: docs/plan/replanned/contracts/254-complete-safe-human-report-supersede.json
successor_plans:
  - docs/plan/active/297-complete-safe-human-report-supersede.md
inherited_acceptance_digests:
  - sha256:0b836365a6f3bd0fba3eef98f87d246fae94acf3271554d925caae270350e43c
integration_source_ids:
  - 254
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
implementation_mode: parent_direct
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Epoch-1 review reproduced that changing a declared source file makes publish --supersede exit 4 before it can publish the new hash and timestamp.","kind":"reproduced_defect"}
  - {"evidence":"verify_shared_report already separates stored-pair parsing, deterministic rendering, publication gates and freshness into callable checks that can be recomposed without weakening verify-shared.","kind":"existing_mechanism"}
  - {"evidence":"The promoted two-file candidate already covers unchanged byte preservation, stale timestamps, conflicted HTML and symlinked HTML; one focused source-change case exposes the remaining boundary.","kind":"bounded_prototype"}
completion_conditions:
  - The replacement path validates the existing report.json and index.html pair for regular in-bound files, parse safety, conflict absence, publication gates and deterministic mutual consistency before any timestamp reuse or write, without requiring the old source hashes to match current repository bytes.
  - An explicit supersede whose prospective shared document differs only in generated_at leaves the verified existing report.json and index.html bytes untouched, including valid noncanonical JSON formatting.
  - An explicit supersede after any non-generated_at change, including a referenced source-file byte change, writes a new timestamp and current source hash and then passes verify-shared.
  - The public verify-shared command retains its existing repository-freshness failure when a recorded source is missing, unpublishable or byte-different, and all unsafe or malformed existing output cases remain fail closed.
completion_witness_map:
  - {"condition_sha256":"sha256:8c2da92dda1853f4430a2b79fe9e9dfab3efbda09c4673b8a3812fd96c6d80e6","witness":"scripts/lint-project-workflow.sh"}
  - {"condition_sha256":"sha256:c045bcad0199722bb68104d41484a5eeb2a8720bec510fe069246520add3a431","witness":"scripts/lint-project-workflow.sh"}
  - {"condition_sha256":"sha256:3f75639654d95a8773c07fff42c681efd559f7d5b788e3db137723fe0e2e5516","witness":"scripts/lint-project-workflow.sh"}
  - {"condition_sha256":"sha256:8854f1a6d0211fedd8bba443e6e1f09de21717c7cafcd58aa1e60a2e73ce2a26","witness":"scripts/lint-project-workflow.sh"}
write_scope:
  - template/.project-agent-workflow/scripts/human-report.py
  - tests/test-human-report.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/replanned/2026/09/01-15/254-preserve-identical-human-report-supersede.md
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
focused_validation:
  - scripts/lint-project-workflow.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Across a UTC-second boundary, an unchanged explicit supersede remains byte-identical while a changed shared report does not inherit stale generation-time provenance.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:0b836365a6f3bd0fba3eef98f87d246fae94acf3271554d925caae270350e43c","stage":"focused","witness":"scripts/lint-project-workflow.sh"}
integration_gates:
  - Continue only in the retained Plan 254 task worktree after the schema-4 reconstruction transition publishes and binds this successor; the promoted dirty bytes remain advisory until corrected, reviewed, validated and committed.
  - Keep verify-shared repository-freshness semantics unchanged. The replacement-only preflight may omit current-source hash equality but must retain stored JSON and HTML path safety, parse, conflict, deterministic-rendering and publication-gate checks.
  - Run the existing-pair preflight before reading reusable provenance or writing either output, and fail without changing either file when that preflight rejects the pair.
  - Preserve both existing files without any write when the prospective document differs only in generated_at; do not canonicalize already verified JSON bytes.
  - Add a regression that changes a referenced source file, crosses a UTC-second boundary, supersedes successfully, observes a new timestamp and current source hash, and then passes verify-shared.
  - Bind a new exact-target adversarial preflight and a fresh formal review to this successor before focused and authoritative validation; do not reuse Plan 254 review or validation evidence.
checked_summary_ja: 変更のない共有レポートは同一バイトのまま保ち、参照元の変更後は安全性を確認して最新の由来情報で再発行できるようにする。

## Decisions

- Stored-pair integrity means the condition that the existing report.json and index.html are regular in-bound files, parse safely, contain no conflict marker, satisfy publication gates, and match through deterministic rendering.
- Repository freshness means the condition that every recorded source remains publishable and its current bytes have the recorded SHA-256, in addition to stored-pair integrity.
- Explicit replacement means one publish --supersede invocation that validates stored-pair integrity before any write, preserves both files when unchanged, and otherwise writes both files with current provenance.
- The unchanged replacement result means the state in which the verified existing report.json and index.html byte sequences remain untouched because the prospective document differs only in generated_at.
- The changed replacement result means the state in which newly written report.json and index.html record the current timestamp and source hashes because a non-generated_at field differs.
- Treat stored-pair integrity and repository freshness as separate predicates.
- Use stored-pair integrity, excluding current-source hash equality, as the precondition for an explicit replacement.
- Keep current-source hash equality mandatory for the public verify-shared result.
- Leave both files unwritten for a verified unchanged replacement so valid noncanonical report.json bytes survive.
- Rebuild both files with a current timestamp and source hashes whenever any non-generated_at field changes.
- Promote both preserved Plan 254 product paths into this parent-direct successor without changing their bytes during reconstruction.

## Tasks

- [x] Extract or parameterize the stored-pair integrity checks without weakening verify-shared freshness.
- [x] Add the source-byte-change replacement regression while preserving every existing unchanged and unsafe-pair regression.
- [x] Run exact-target preflight, formal review, focused validation and the authoritative suite once.
- [x] Commit the reviewed two-file patch, archive this successor, and publish the retained task worktree.

## Validation Notes

- Owner continuation authorization: `完了させるためにプランを修正し、作業せよ。`
- Plan 254 epoch 0 and epoch 1 execution ledgers remain immutable.
- Plan 254 epoch-1 formal review found one High acceptance gap on the exact promoted target: a legitimate source-byte change is rejected before replacement.
- Full decision audit: `.agent-artifacts/decision-audits/254-source-change-supersede-reconstruction.md`.
- Required referent contract: `.agent-artifacts/referent-contracts/297-safe-human-report-supersede/contract.json`.

- Accepted product commit: `16ad1c6b25ec5065d9ac12a2e374c7117465bf49`; its complete diff against the execution baseline equals the reviewed two-file patch.
- Exact-target adversarial preflight and independent epoch-1 review passed with High 0, Medium 0 and Low 0; the parent verified and accepted the evidence.
- Owner-authorized alternate review evidence uses the actual reviewer transcript and result; no synthetic runtime hook event was admitted.
- Focused validation: `scripts/lint-project-workflow.sh` passed once.
- Authoritative validation: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` each passed once; the shared-report suite passed all 14 tests. Optional actionlint checks were skipped because actionlint was unavailable.
- Local evidence: `.agent-logs/plan297-epoch1-review/manifest.json` and `.agent-logs/plan297-epoch1-validation/manifest.json`; missing transcript or hook sources are explicitly recorded in those manifests.
- No unresolved implementation findings remain. File writes are confined to retained directory descriptors; pair-level atomicity and an unrestricted same-user actor replacing every process and object remain outside the accepted guarantee.
