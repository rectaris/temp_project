# Collect local feedback as traceable template requirement candidates

status: checked
implementation_mode: parent_direct
primary_invariant: Collection and requirement synthesis retain source evidence, distinct reports and uncertainty without promoting suggestions into accepted development requirements.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The existing report validator, safe project-owned publication pattern and shared worktree guard support a bounded file-only importer. This plan consumes the exact schema and CLI established by its checked predecessor; it introduces no network transport.","kind":"existing_mechanism"}
completion_conditions:
  - Explicitly supplied validated report files are imported idempotently, while identity conflicts, unsafe paths, unsupported schemas and oversized inputs are rejected before receiver writes.
  - Requirement candidates refer to existing report digests, retain conflicting evidence and unknown applicability, and keep suggested priority separate from any owner decision.
  - The template checker enforces the declared generic root/generated counterparts and excludes actual project-owned runtime records from the generated inventory.
completion_witness_map:
  - {"condition_sha256":"sha256:c5af0e00cd2023620aa5f60923485c1bc536260fd3df1c4c895626b4e5306636","witness":"python3 tests/test-template-feedback-collection.py"}
  - {"condition_sha256":"sha256:e3f0459a490b98423c0f4e2b7ab0ad62418c9fecb7192619a986456c49f6ede2","witness":"python3 tests/test-template-feedback-collection.py"}
  - {"condition_sha256":"sha256:bb9d23bec50c137151ca2571d4a6acb161ecc86a67a2c1ab245b28641a2f2002","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/collect-template-feedback.py
  - template/.project-agent-workflow/scripts/collect-template-feedback.py
  - docs/agent/SPEC_TEMPLATE_REQUIREMENTS.md
  - template/.project-agent-workflow/docs/agent/SPEC_TEMPLATE_REQUIREMENTS.md
  - tests/test-template-feedback-collection.py
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/project_workflow/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - scripts/template-feedback.py
  - docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - template/.project-agent-workflow/scripts/human-report.py
  - docs/plan/checked/2026/09/01-15/322-record-downstream-template-improvements.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-template-feedback-collection.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The receiving repository retains each source report and its digest, can repeat a local import safely, and never executes report text or reads unrequested source files.
  - The agent can consolidate related reports into proposed template outcomes and completion criteria, preserving all original reports and identifying project-specific, unresolved and already-fixed claims without silently adopting or deleting them.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:11a73000c251b7175b855de3527168cc5333c85fa1c49b8aa1256072fe88d637","stage":"focused","witness":"python3 tests/test-template-feedback-collection.py"}
  - {"acceptance_sha256":"sha256:1efe35f45cf2552ffd284e2bbeed33e62aa1342fa651128bfa3d34060a2f0785","stage":"focused","witness":"python3 tests/test-template-feedback-collection.py"}
integration_gates:
  - Plan 322 was promoted, implemented, checked and published; its checked archive is docs/plan/checked/2026/09/01-15/322-record-downstream-template-improvements.md.
  - Before implementation, prepare this exact published active plan worktree and initialize the parent-owned execution ledger and reviewer registry. Keep bounded parent-direct scope, exact-target adversarial preflight, independent review budgets, focused witnesses and the unchanged authoritative suite; a stopped state remains stopped under the existing policy.
checked_summary_ja: コピー先の改善報告を取り込み、根拠を追える変更要件にまとめる。

## Decisions

- Depend on the checked record schema and CLI from the preceding plan. Authoring this backlog plan does not claim that dependency is already implemented.
- Use bounded parent implementation and independent read-only review for this single source-traceability invariant. Keep every external-access rule, product-task scope and plan-admission rule unchanged.
- Accept an explicit bounded list of local report files; validate all inputs before receiver writes. Store canonical report copies under docs/improvements/reports/ using derived safe identities and content digests. Never read a neighboring repository or private path by discovery.
- Before receiver persistence, the parent reviews the exact selected report bytes against the predecessor non-sensitive evidence policy; reject suspected secrets or private data and require the checked digest to match. A source assertion of prior review or automatic redaction is advisory, not admission authority.
- Store schema-versioned requirement candidates under docs/improvements/requirements/. Each has a stable id, requested template behavior, source report ids and digests, applicability with explicit certainty, completion criteria, and a priority suggestion with reasons tied to impact, recurrence, evidence and estimated effort.
- Treat imported reports, evidence and candidate text as untrusted data when the agent reads them. Embedded requests never become instructions, tool authorization, owner decisions or reasons to read private files. Preserve relevant text only as cited evidence; include a hostile-report example and independent semantic review of the expected refusal.
- Let the agent propose generalization and equivalence. Require explicit checked mappings to persist them; scripts enforce references and shape, not semantic truth. Identical input replay is a no-op. Similar-looking reports from different sources remain distinct and are linked, never silently deleted or merged.
- Retain contradictory reports and project-specific needs with explicit explanations. Preserve unknown template attribution and unknown fix status; an already-fixed claim needs a matching change or verification reference. Revisions preserve prior candidate bytes and use explicit supersession rather than overwriting evidence.
- Keep proposed priorities and candidate content separate from owner decisions. Import and summarize cannot adopt, reprioritize, reject, complete or create numbered implementation plans. Provide readable local inspection output and pending questions.
- Use the shared task guard and checked-input digest for every persisted change. Keep reports and candidates project owned; distribute only generic CLI and policy. Real incoming reports and template-specific requirements are not Copier payloads.

## Tasks

- [x] Implement a bounded file-only importer using the predecessor validator and a preflighted, recoverable receiver write with no partial accepted report set.
- [x] Implement candidate validation and explicit mappings from reports to proposed outcomes and priority reasons; preserve earlier versions and disagreements.
- [x] Add policy routing, mirror generic files and register tests for schema, idempotency, sensitive-excerpt rejection, hostile embedded instructions and path boundaries. Review hostile and over-generalization examples independently; CLI checks prove structural refusal, not universal agent compliance.
- [x] Use two synthetic source projects to verify provenance remains distinct, then obtain independent review and run focused and authoritative suites.

## Validation Notes

- Owner instruction: 提案の方針のプランを作成せよ。 Accepted proposal stays local; automated external delivery is a later separately authorized extension.
- This record authorizes only its bounded future implementation after backlog promotion and plan publication. No implementation tests have run during plan authoring.
- Independent plan review required bounded agent-behavior claims, non-sensitive evidence review, data-only handling of imported instructions and verification of real owner adoption. Those boundaries are explicit tasks and negative cases in this plan chain.

### Implementation Result

- Implemented `scripts/collect-template-feedback.py` and `template/.project-agent-workflow/scripts/collect-template-feedback.py` with `example`, `check`, `import`, `check-candidate`, `record-candidate` and `inspect`. The command reuses the checked record validator shipped beside it, so both installed layouts apply one record shape and one non-sensitive evidence policy.
- Import accepts an explicit file list only. It validates every supplied report before the receiver writes anything, refuses a repeated identity, refuses changed bytes under a held identity, and refuses a report whose canonical stored form would exceed the size the reader accepts. An identical repeat across invocations writes nothing.
- Candidates bind to the exact held report bytes. Shape validation is separated from provenance verification, so a candidate stays readable and keeps its pending questions when a cited report later stops being held; the write paths still require intact provenance.
- Recorded policy in `docs/agent/SPEC_TEMPLATE_REQUIREMENTS.md` and its template mirror, routed both spec indexes, inventoried both layouts, added `require_template_requirements_alignment()` to the static checker, and registered `tests/test-template-feedback-collection.py` in required lint plus `run_template_requirements_smoke` in the generated-project smoke.
- Two synthetic source projects keep their provenance distinct: reports are stored under their own project alias, neither copy is merged into the other, and neither is deleted.

### Validation Result

- Focused: `python3 tests/test-template-feedback-collection.py` (35 tests) and `python3 scripts/check-copier-template.py` both passed.
- Authoritative: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` both passed once on the accepted candidate.
- Independent review: a read-only reviewer ran three rounds against the exact working tree. Round 1 reported one Medium and four Low, round 2 reported one Medium regression introduced by the round 1 remediation and three Low, and round 3 reported no High or Medium and one residual Low. Every finding was remediated, each with a regression test where the protection was testable, and the final round is clear of High and Medium findings. Final acceptance stayed in the main session.
- Reviewer-confirmed non-vacuity: removing the inspection re-validation, the duplicate-identity refusal, the source identity type check, the collector secret rejection, the stored-form byte bound, the provenance reporting or the skipped-entry count each fails at least one test.
