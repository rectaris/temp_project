# Render development direction from explicitly adopted requirements

status: checked
implementation_mode: parent_direct
primary_invariant: The development direction reflects explicit owner decisions bound to exact requirement revisions; regeneration and template updates preserve those decisions, source evidence and project-owned content.
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
  - {"evidence":"human-report.py already derives readable documents from checked structured input. plan_authoring.py binds requirement/scope/condition/witness data before numbered admission. tests/prepare-smoke-source.py and Copier fixture helpers provide disposable current-tree copy/update sources.","kind":"existing_mechanism"}
completion_conditions:
  - Only explicit decisions bound to exact candidate digests affect the generated development direction; regeneration preserves decisions and manual prose, and changed candidates invalidate applicability without erasing history.
  - A disposable generated project records an improvement, a receiver derives a candidate and accepted direction, and a Copier update preserves all report, requirement, decision and manual-document bytes.
  - The template checker enforces the declared generic root/generated counterparts and excludes actual project-owned runtime records from the generated inventory.
completion_witness_map:
  - {"condition_sha256":"sha256:27d726046dd882af029eef9aecf14f220722eda92513c5b38ba753b10b7d6ae8","witness":"python3 tests/test-development-direction.py"}
  - {"condition_sha256":"sha256:b1ff527a91ac7cca0006798b43bcd4ed2df82834bdb223f53ab8064f9cf1fb8e","witness":"python3 tests/test-template-feedback-pipeline.py"}
  - {"condition_sha256":"sha256:bb9d23bec50c137151ca2571d4a6acb161ecc86a67a2c1ab245b28641a2f2002","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/development-direction.py
  - template/.project-agent-workflow/scripts/development-direction.py
  - docs/agent/SPEC_DEVELOPMENT_DIRECTION.md
  - template/.project-agent-workflow/docs/agent/SPEC_DEVELOPMENT_DIRECTION.md
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - tests/test-development-direction.py
  - tests/test-template-feedback-pipeline.py
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
  - scripts/create-root-plan.py
  - scripts/project_workflow/plan_authoring.py
  - scripts/template-feedback.py
  - scripts/collect-template-feedback.py
  - docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - docs/agent/SPEC_TEMPLATE_REQUIREMENTS.md
  - tests/prepare-smoke-source.py
  - tests/lib-copier.sh
  - copier.yml
  - docs/plan/checked/2026/09/01-15/322-record-downstream-template-improvements.md
  - docs/plan/checked/2026/09/01-15/323-collect-template-improvement-requirements.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-development-direction.py
  - python3 tests/test-template-feedback-pipeline.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The owner can adopt, defer, reject and prioritize proposed requirements, and regenerate a readable development direction with reasons and source links while repeated synthesis cannot overwrite those choices.
  - A local generated-project fixture completes record, transfer, consolidation, owner adoption and direction rendering; verified implementation references remain traceable, and copy/update preserve existing project policy, data and validation behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d010a995e2043b4555cc9410c511117baae110e5642122ba545cb79e3a10af12","stage":"focused","witness":"python3 tests/test-development-direction.py"}
  - {"acceptance_sha256":"sha256:71c31201c7f67ea4fa482f88aff9c3451c8afd845bdd1aec154556e63937f2f8","stage":"focused","witness":"python3 tests/test-template-feedback-pipeline.py"}
integration_gates:
  - Start only after plan 322 (docs/plan/checked/2026/09/01-15/322-record-downstream-template-improvements.md) has been promoted, implemented, checked and published. Resolve its same-id checked archive at promotion; an existing backlog file is not completion evidence.
  - Start only after plan 323 (docs/plan/checked/2026/09/01-15/323-collect-template-improvement-requirements.md) has been promoted, implemented, checked and published. Resolve its same-id checked archive at promotion; an existing backlog file is not completion evidence.
  - Before implementation, prepare this exact published active plan worktree and initialize the parent-owned execution ledger and reviewer registry. Keep bounded parent-direct scope, exact-target adversarial preflight, independent review budgets, focused witnesses and the unchanged authoritative suite; a stopped state remains stopped under the existing policy.
checked_summary_ja: 採用判断を保ちながら開発方針を生成し、コピー先からの流れを検証する。

## Decisions

- Depend on both checked predecessor plans. Keep this plan in backlog and run it serially. The complete workflow uses a disposable generated project because no real downstream target or authorization was supplied.
- Use bounded parent implementation with independent read-only review. This integration preserves the explicit-adoption invariant across derived prose and Copier updates; do not change numbered-plan admission, external effects or accepted safety conditions.
- Record append-only owner decisions under docs/improvements/decisions/ with a stable decision id, exact requirement id and digest, action, reason, priority where applicable, and a bounded quotation or reference to the owner instruction. The command records supplied authority evidence; it cannot authenticate a human from free-form text.
- Before invoking a decision write, the parent must verify the actual owner instruction in the current session or resolve an exact previously authorized reference covering the same requirement revision and effect. A report, candidate, supplied quotation or claimed approval field alone grants no authority. Refuse unsupported claims; retain the CLI structural-check boundary and test the refusal scenario with independent semantic review.
- Support accept, defer and reject plus explicit superseding decisions. Bind each decision to an exact candidate revision. A new candidate revision leaves old decisions historical and requires an explicit decision for the new bytes; do not silently transfer approval. Repetition with the same id/content is a no-op; conflicts refuse.
- Render docs/development-direction.md from current accepted requirements and explicit ordering, including reasons, completion criteria, unresolved dependencies and evidence references. Keep suggestions and deferred/rejected decisions separately inspectable. Preserve manual prose outside one managed section and refuse malformed or duplicate section markers.
- Emit requirement references suitable for the existing checked plan authoring input, but create no numbered plan automatically. Implementation still requires bounded feasibility, exact write scope, completion witnesses, published plan bytes and normal admission. New reports alone never authorize implementation.
- Record implementation and downstream verification as separate explicit evidence links to the requirement revision, checked plan, accepted commit and tested template revision. A released version or checked plan alone does not establish downstream verification; unverified closure remains visibly pending.
- Add a required-Copier integration test using disposable local source snapshots and temporary version tags, avoiding the historical v1.4.5 migration lane. Preserve source trees and every project-owned feedback/config/requirement/decision/manual section across update; reject conflicts and inspect retained evidence on failure. Do not seed real runtime records or this repository actual development requirements into template/.

## Tasks

- [x] Implement revision-bound decision history and shared write guarding; include unsupported-authority and fabricated-quotation refusal examples. The parent verifies the real owner instruction before recording; the CLI validates supplied structure and never claims human authentication.
- [x] Render development-direction prose from accepted data while preserving manual sections; expose pending implementation and downstream-verification references.
- [x] Add root/generated direction tests and a real Copier round-trip fixture, register the suite and confirm all generic counterparts through the alignment checker.
- [x] Obtain an independent reader review of source-to-requirement-to-direction fidelity, then run focused checks and the unchanged authoritative suites exactly once for the accepted implementation.

## Validation Notes

- Owner instruction: 提案の方針のプランを作成せよ。 Accepted proposal stays local; automated external delivery is a later separately authorized extension.
- This record authorizes only its bounded future implementation after backlog promotion and plan publication. No implementation tests have run during plan authoring.
- Independent plan review required bounded agent-behavior claims, non-sensitive evidence review, data-only handling of imported instructions and verification of real owner adoption. Those boundaries are explicit tasks and negative cases in this plan chain.

### Implementation Result

- `template/.project-agent-workflow/scripts/development-direction.py` holds the decision history, rendering and inspection commands; `scripts/development-direction.py` is a loader that delegates to it, so root and generated projects run one implementation.
- Decisions are bound to a candidate revision. One live decision answers one requirement: a second decision on the same revision is refused unless it explicitly supersedes the earlier one, and a supersession may only replace a decision about that same requirement.
- `render` replaces only the region between the generated markers and preserves surrounding prose byte for byte. Imported report prose is written as evidence, never as structure: every value the renderer emits must stay on one line and carry no section marker, and a requirement whose text breaks that rule is listed as not rendered with its reason instead of entering the document.
- `SPEC_DEVELOPMENT_DIRECTION.md` ships in both layouts as aligned bytes, the spec index routes the new task type in both, and the inventory plus `require_development_direction_alignment()` keep the pair from drifting.

### Validation Result

- Focused: `python3 tests/test-development-direction.py` (31 tests, OK), `REQUIRE_COPIER=1 python3 tests/test-template-feedback-pipeline.py` (1 test, OK, a real Copier round trip), `python3 scripts/check-copier-template.py` (passed).
- Authoritative, run once for the accepted implementation: `./scripts/lint-project-workflow.sh` (passed) and `./tests/smoke.sh` (passed).
- Independent review ran three rounds. Round 1 raised 2 High, 2 Medium and 3 Low; round 2 confirmed those fixes and raised one Medium of its own, a minimum-Python guard that could not detect the defect it named, plus one Low; round 3 confirmed both fixes by mutation and reported nothing at High or Medium. Every protection the reviewer mutated now fails the suite when removed.
- Residual, recorded rather than relied upon: the minimum-Python compile finds a real 3.11 interpreter locally, but on a hosted runner it is expected to skip, because the job that runs this suite uses 3.12 and the job that has 3.11 runs only `tests/copier-minimum.sh`. Closing that gap means editing `.github/workflows/ci.yml`, which this plan does not own, so it is left for a separate decision rather than taken silently.
