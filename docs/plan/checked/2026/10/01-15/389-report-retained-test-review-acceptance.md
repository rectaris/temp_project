# Report retained test evidence separately from review and acceptance

status: checked
primary_invariant: Read-only evidence reporting never changes retained source bytes, run state, spent resources, execution permission or acceptance gates.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Published f254 controller validates retained event chains and derives validation/review counters; adopted runner stores digest-bound diagnostic and validation reports independently of final review.","kind":"existing_mechanism"}
  - {"evidence":"Root and generated controllers have an enforced mirror, existing focused state tests and unchanged locked lint/smoke. No PR1 acquisition helper or live adoption is needed for a read-only reporting consumer.","kind":"existing_mechanism"}
completion_conditions:
  - Matching retained test receipts remain visible when review is absent; diagnostics and formal validation retain their original evidence class, target and missing-field status.
  - Missing, failed or unattributed final review stays incomplete; an interim message or requested identity cannot become a clearing verdict.
  - The report shows existing acceptance holds and original stop reasons separately; reporting alone never grants execution, completion, shipment or candidate adoption.
  - Malformed, stale or wrong-target inputs remain explicit and cannot become pass; reporting changes no retained file, event, consumption counter or existing gate result in root or generated layout.
completion_witness_map:
  - {"condition_sha256":"sha256:83c5cfc0e34503d4ab19fc3ccbd3930926b79d9c4cb4022487da09db82baa78d","witness":"python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest"}
  - {"condition_sha256":"sha256:e8f990fbffd581888f8614dcad93130e37fa78ea67ad8d3ba77eef4c3ab82849","witness":"python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest"}
  - {"condition_sha256":"sha256:9c7e2c8beea37684dabbd8725388253b7e785fa42de0a7c92100c2005ad9b059","witness":"python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest"}
  - {"condition_sha256":"sha256:a98aad048e43ea4a53331322cd4d9be86dfb29beef16e41af55abd514ca16314","witness":"python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
preservation_scope:
  - none
context_files:
  - docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - For one exact retained target, the read-only report independently shows test evidence, reviewer outcome and existing acceptance holds, while preserving provenance/missing data and leaving all source bytes, budgets and operational gate decisions unchanged.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:356c72a48ac15ceb057f18df878bff0c734fa7fd82d09145003d072a49e179f9","stage":"focused","witness":"python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest"}
integration_gates:
  - Publish this aligned existing389 plan through the formal direct-task publisher to refs/heads/issue18/retained-evidence-state-report-20261011 before any product implementation. Preserve the old24a80 provisional candidate and its source record; do not publish that candidate to its drifted source.
  - After plan publication, prepare a distinct plan389 implementation worktree with the same exact source-ref and a fresh prepare-parent-direct ledger, reviewer registry, continuation registry and lifecycle identity. Keep all old ledgers and registries unchanged.
  - Use only the explicit389-scoped owner authorization Sentinel_87a75c5dbcc081918eec82cb2ca5ed90 at2026-10-11T11:14Z for limited start/review evidence. Fix actual scope, diff and test results for a separate read-only review; keep packet-start observation and context-isolation guarantees unconfirmed. Do not rerun the unchanged native probe or record fabricated formal route/review events.
  - The three exact tooling/test paths are parent-owned validation-authority paths. Use bounded parent-direct implementation and independent read-only code/spec/evidence review; do not change candidate-worker denials, controller gates, canonical event consumption or validation definitions. Preserve one initial review and at most one correction confirmation; unresolved findings stop for the parent without resetting consumed history.
  - After focused tests, unchanged locked lint/smoke and exact-target limited-review clearance, normal commit and formal local publish to the bound source, then normal push and one draft PR to dev and same-SHA CI. Include accepted392 closure as dependency. Confirm restoration and no other task use before automatic current-task retirement. No main/dev direct push/merge, force, release or old safety-refusal retry.
checked_summary_ja: テスト証拠・レビュー結果・受入保留を独立して表示する

## Decisions

- Add a bounded read-only consumer of existing retained controller events and runner report references; do not add a second canonical ledger or storage framework.
- Keep diagnostics, captured test result and accepted validation distinct; missing environment/input/expectation fields remain missing.
- Do not alter review-route requirements, start/check/completion predicates, reviewer budgets or authoritative validation definitions in this unit.
- Keep Plan387 whole E1-E5 requirements and retained ba8657 supplement unchanged. This unit is not a descope, successor or review-budget reset.
- Implement this inseparable controller/report/test slice through bounded parent-direct work with the same focused, final independent-review and authoritative validation gates. Its reporting behavior does not change validation authority.
- The owner explicitly changes start/review evidence criteria for389 only; implementation and publication use the bounded human-reviewed path above. This changes no canonical controller gate or product acceptance predicate and cannot authorize387, E1-E5 or oldPR1 adoption.

## Tasks

- [x] Implement bounded read-only reporting using adopted validators and exact retained target/provenance fields.
- [x] Add the planned root/generated focused tests and confirm input bytes and existing gate outcomes are unchanged.
- [x] Run focused cases, exact-target independent quality review and unchanged locked lint/smoke through the admitted task workflow before publication.

## Validation Notes

- Owner instruction supplied by parent: 提案の方針で作業を進めよ。 Source Sentinel_82a1465647b4819189fac16681b59e5e at2026-10-10T16:53:09.716456Z.
- Public dev exact baseline f254ae2036d5e08f02a8bc3165cc4656c1c1a89f; local dev81 commits never imported.
- Issue18 section4 agreed insertion was saved under explicit owner approval Sentinel_cb80ea9b86cc8191958bbff6e83d00ad. Actual remote readback at2026-10-10T17:23:37Z exactly matches the saved payload; original body and E1-E5 retained. This specification publication does not change or adopt operational gates.
- The witness describes future unit tests, not a passing run. No original failure cause, live PR1 acquisition, clearing quality review or whole E1-E5 acceptance is claimed.
- The owner-approved minimal reporting scope, source approvals, past successful hook/transcript capture and current hook support are reused from retained evidence; no approval-source or hook-support reinvestigation is required. A new execution-specific capture is still unfulfilled.
- Parent delegation on2026-10-11 permits concrete active-plan authoring and execution connection on the existing branch, with no new deletion authority, main/dev integration, old review25 or refused namespace retry, or PR20 review/state change.
- Authoring source HEAD is ba8657ba3b1e52013392f3c148008a5cca1f5bb3 on refs/heads/issue18/plan387-independent-fixtures-20261010; public dev ancestry is f254ae2036d5e08f02a8bc3165cc4656c1c1a89f. Plan387 backlog, all E1-E5 requirements and the retained PR1 candidate remain untouched.
- This fresh report unit has no predecessor ledger and reuses no stopped run, budget or restoration authority. Missing old evidence remains missing and unknown.
- Current authoring source HEAD540ac827ec8d85f1f537ceb6447e912b6b14655a is one scoped392 closure commit atop latest public dev2da8ed6ee7af71e1e5ce476c4f73e0c8003e0405, on refs/heads/issue18/retained-evidence-state-report-20261011. Local dev81 commits are excluded. Earlier source/baseline/cleanup statements above are retained history and superseded by current integration gates.
- Current owner verbatim instruction: 提案の方針で進めよ。 Source Sentinel_87a75c5dbcc081918eec82cb2ca5ed90 at2026-10-11T11:14Z, approving proposed389-only implementation start, limited review evidence and publication after clearance. Parent delegation permits the established3path report with needed regressions/document alignment and one meaningful draft PR containing392 closure.
- Runtime first-packet observation, zero inherited context and runtime isolation remain unconfirmed. The prior unchanged producer/probe evidence is retained; no repeat probe, formal runtime clearance or stopped-run recovery is claimed. No389 implementation review has yet been spent; first review and at most one correction confirmation retain their actual results and target hashes.
- 392 is checked under its approved limited criterion. Its completion is neither387 start permission nor E1-E5/livePR1 acceptance; all original backlog requirements, unassigned reasons and safety holds remain.
- Current389 completion evidence at2026-10-11: the product commit is a941f5f3ded3ac06c5aee4545db91d72159318b9, exactly one child of published authoring9adbb85d156cf27fd2ce43a05212411c4a337d43. Its full-index3path patch SHA-256 is1ebddc9dd875bf841d5c9b03ffad9bb0cc27ccb41314ed98b1bac5faf00e5025; root/generated report scripts match byte-for-byte and all pre-existing gate, mutator and test bytes remain unchanged.
- Focused validation `uv run --locked python3 tests/test-plan-execution-state.py RetainedEvidenceStatusTest` passed9cases on the exact final patch. The initial focused run failed because two new synthetic fixtures omitted the mandatory invariant digest; its raw failure and bounded diagnosis remain retained. The fixtures were corrected without changing existing assertions or authority.
- Limited read-only review1 found2Medium defects: contradictory captured-test pass display and unattributed global acceptance display. Both were corrected within the same3paths; review2 returned `REVIEW-VERDICT: none` for the exact final patch and focused receipt. Both actual review starts/results and original hashes are retained;2of2 limited reviews are consumed, with no continuation, successor or budget reset. Main-session exact-target acceptance followed that review. The requested change_reviewer/Sol-high profile is not a runtime attestation.
- Required validation was executed once each after the acceptable final review in this task worktree: `uv run --locked scripts/lint-project-workflow.sh` exit0,317.501seconds; `uv run --locked tests/smoke.sh` exit0,112.230seconds. Commands, fixture locations and HOME were unchanged, with formal minimal host execution approval. A prior static mirror check could not open the default uv cache in the normal sandbox; the same check passed under formal approval, separately retained as an environment-only incident.
- All4completion conditions and the single acceptance digest retain their original focused witness. The regressions cover matching receipts with missing metadata, diagnostic/formal classes, absent/interim/unattributed review, stale/contradictory inputs, bounded malformed files, source-byte and gate preservation, attributed ledger review, and candidateA correction followed by candidateB acceptance queried asA. Run-wide acceptance is explicitly global and target closure remains unattributed by this reader.
- Completion uses only the explicit389 owner criterion stated above. The fresh prepared389 execution ledger remains unchanged with no fabricated review-route, formal review, writable-attempt or canonical accepted-close event. Runtime packet-start observation, zero inherited turns and runtime isolation remain unconfirmed. This local unit completion never supplies those guarantees,387 execution permission, E1-E5 acceptance or PR1 adoption.
- Persistent measured stdout/stderr, receipt digests, both verbatim reviewer reports, target records, private-state snapshots and protection inventories are retained under `.agent-artifacts/issue18-plan389-implementation-20261011/`. A current full transcript and hook event source were not collected as formal execution evidence; both absences remain explicit in the run manifest.
- Before product completion, the protected PR1 inventory2641items and shared-existing evidence/registry inventory18905items remained identical, together with387/418, old38924a80 authoring, old392 ledger and main/dev. The earlier source-ref omission created an effect-free direct task bound to dev; it was caught before a repository write and retained unchanged. Its stopped-retirement ancestry is not proven eligible, so no alternate deletion or owner-record rewrite was attempted. A local template-feedback draft records this operating error with revision/attribution unknown; no tracked improvement record is persisted in this product task.
