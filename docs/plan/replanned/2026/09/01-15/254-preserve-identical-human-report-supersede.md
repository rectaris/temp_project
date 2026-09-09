# Preserve identical shared-report supersedes

status: replanned
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The unchanged supersede test fails at a UTC-second boundary because shared_document recomputes generated_at before rendering.","kind":"reproduced_defect"}
  - {"evidence":"The existing validated shared document already contains every field needed to distinguish unchanged from changed publication content.","kind":"existing_mechanism"}
completion_conditions:
  - When every shared-document field other than generated_at is unchanged, publish --supersede reuses the validated existing generated_at value and reproduces byte-identical report.json and index.html files.
  - When any shared-document field other than generated_at changes, publish --supersede keeps the newly generated UTC timestamp.
completion_witness_map:
  - {"condition_sha256":"sha256:92ce992988b36acd726bb75c918d0e1e500e0c154439d03a231983228a5c2899","witness":"python3 tests/test-human-report.py"}
  - {"condition_sha256":"sha256:9612c9e8a08339452016e59e5712d8c395fe7198f58753087194246c8bd556a7","witness":"python3 tests/test-human-report.py"}
write_scope:
  - template/.project-agent-workflow/scripts/human-report.py
  - tests/test-human-report.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/active/108-orchestrate-supervised-orca-workers.md
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
focused_validation:
  - python3 tests/test-human-report.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Across a UTC-second boundary, an unchanged explicit supersede remains byte-identical while a changed shared report does not inherit stale generation-time provenance.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:0b836365a6f3bd0fba3eef98f87d246fae94acf3271554d925caae270350e43c","stage":"focused","witness":"python3 tests/test-human-report.py"}
primary_invariant: preserve the complete coupled source acceptance baseline
replan_sources:
  - docs/plan/active/254-preserve-identical-human-report-supersede.md
replan_contract: docs/plan/replanned/contracts/254-complete-safe-human-report-supersede.json
integration_gates:
  - combined successors must satisfy every mapped source acceptance item
successor_plans:
  - docs/plan/active/297-complete-safe-human-report-supersede.md
inherited_acceptance_digests:
  - sha256:0b836365a6f3bd0fba3eef98f87d246fae94acf3271554d925caae270350e43c
checked_summary_ja: 内容が変わらない共有レポートの再発行結果を同一に保つ。

## Decisions

- A publish --supersede invocation whose validated report, source commit, source hashes, report id, schema version, and generator version equal the existing shared report.
- The generated_at value already stored in the validated existing shared report when every other shared-document field equals the prospective replacement.
- A publish --supersede invocation for which at least one validated shared-document field other than generated_at differs from the existing shared report.
- Preserve generated_at only for exact shared-document equality after removing that one field from both documents.
- Fail closed on an unsafe or malformed existing shared document instead of using it as supersede provenance.
- Do not weaken the byte-identical regression assertion.

## Tasks

- [ ] Implement conditional generated_at preservation for identical explicit supersedes.
- [ ] Make the UTC-second-boundary regression deterministic and cover changed-report provenance.
- [ ] Review, validate, archive, and publish the repair before resuming Plan 108 in a fresh run.

## Validation Notes

- Plan 108 authoritative validation failed once at tests/test-human-report.py:292 and its stopped execution ledger confirmed one independent repair invariant.
- The repair classification review bounded changes to the managed human-report script and its focused test.
- This plan's authoritative validation failed before the human-report tests because its newly prepared worktree materialized both tracked pre-commit hooks as `0775` under umask `0002`, while repository validation requires exact mode `0755`.
- Independent diagnosis confirmed one worktree-materialization invariant, and independent classification recorded `repair_required`; the staged human-report candidate remains preserved unchanged for a fresh run after that repair is checked.
- Plan 292 is checked at `docs/plan/checked/2026/09/01-15/292-normalize-managed-worktree-hook-modes.md`; a newly prepared Plan 254 worktree materialized both required hooks as exact mode `0755`, so this plan resumed from a fresh source baseline.
- Epoch 1 formal review reproduced that the full freshness verifier blocks `publish --supersede` after a legitimate source-byte change, so the replacement path cannot restore current provenance.
- The required correction must separate replacement-time stored-pair integrity from repository freshness while keeping unsafe-path, conflict, deterministic-rendering, and publication-gate checks fail closed; this changes the overwrite validation boundary and is recorded as `security_boundary_drift`.
- The stopped epoch-0 and epoch-1 ledgers remain immutable. Owner instruction `完了させるためにプランを修正し、作業せよ。` authorizes a requirement-preserving successor.
