# Reject malformed active-plan indexes before lifecycle work

status: backlog
primary_invariant: Every root and generated-project check or lifecycle mutation treats the active-plan index as either one exact empty representation or one exact TSV representation, rejects every other nonempty form before mutation, and every writer emits only those representations.
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"In a disposable root-check fixture, two actual-tab in_progress rows were rejected, while the same header and rows written with literal backslash-t separators returned success because no header was recognized."}
  - {"kind":"existing_mechanism","evidence":"Generated planlib.py already owns active-index reads and canonical writes under the lifecycle lock, and lint-plan-docs.py already validates index identity, paths, and manifest status."}
  - {"kind":"existing_mechanism","evidence":"Root complete-plan.sh already performs two-file rollback and finalize-active-plan.sh already checks one exact indexed plan before archival, so strict pre-mutation parsing fits existing transaction boundaries."}
completion_conditions:
  - Root and generated readers accept only the exact empty marker or one actual-tab header followed by normalized three-column rows, and reject missing, repeated, escaped, mixed, or otherwise malformed nonempty content.
  - Empty and nonempty writers emit their single canonical representation with one trailing newline and never copy malformed input into new output.
  - Root completion and finalization parse and validate the complete active index before their first repository mutation and preserve plan, index, archive, and checked-index bytes on rejection or write failure.
  - Generated create, promotion, status-change, completion, and finalization operations validate the complete active index through the shared lifecycle code before their first mutation and preserve original bytes on failure.
  - Root and generated restructuring validate the complete current index and proposed replacement before their commit point and preserve original bytes when either representation is invalid.
  - Root policy, generated policy, lifecycle behavior, and Copier parity checks enforce the same accepted representations and failure boundary.
  - Regression fixtures cover actual tabs, literal backslash-t text, absent or duplicate headers, wrong column counts, stray content, mixed empty markers and rows, duplicate identities, missing paths, and manifest-status mismatch.
completion_witness_map:
  - {"condition_sha256":"sha256:89c5a9b93e756350370dfe3ede7d600f320333c685030cdf13c7be6b31508b04","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d7a192e4a30063ae16301b2efab17ac36834b6765cd61c106e5a68d96171a9b0","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:88a2b5d0f5321e34644187595d8732c3666e5c8c556d9642b0d024127ef8284c","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:4288d131c823f8fd36aebdb741a07d4ee0e74fdafe315043d2ebabc590f2fddb","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:4460e7250099d22e4f66ec6d60c76c97f68746181771ced8db6188d5bef058e3","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:a3dfdc5e8115044805115f50fe456a81fc6a55fed8086287ee8818710f1b0859","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:eb7a13ba5560115583058bf1b7b7dc6256fbd6cabfc7c685223135f06765d35f","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/check-root-agent-policy.py
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - template/.project-agent-workflow/scripts/planlib.py
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/complete-plan.sh
  - template/.project-agent-workflow/scripts/finalize-active-plan.sh
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/check-copier-template.py
  - tests/validation_tools/plan.py
  - tests/root-plan-lifecycle.sh
  - tests/test-plan-restructure.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/plan_validation_commands.py
  - template/.project-agent-workflow/scripts/create-plan.sh
  - tests/validation_tools/support.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/plan_validation_commands.py --self-test
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Reject every malformed nonempty active-plan index in root and generated-project checks instead of interpreting it as an empty list.
  - Make root completion and finalization validate the whole index before writing and preserve all existing plan and index bytes when validation or writing fails.
  - Make generated planlib-backed lifecycle mutations validate the whole index before writing and preserve existing bytes on failure.
  - Make root and generated restructuring reject an invalid current or proposed index before the commit point and preserve existing bytes on failure.
  - Keep root and generated policy and lifecycle behavior aligned while preserving the exact canonical empty and populated output forms.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:89d8d14bcf32df3461bb2ecf3dfcb96eb69379f47637d1f7e8f34ec1c118aa22","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:cd86c8a09d3c90640ed3b22e7abd76076dd049a98474c4865296d6e3d07366cd","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:90dc2b620b7ab6082b37f9478ebbec667dd46f1d98bb29dd618aee5feb4ee1b0","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:0bab2bf33a6fc8b2c1e0e7d7d50256a33b96b1aae72080d10da202ea451e6812","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:4a6dfe63f1a678add3beba80b4fc33e200508a5de3cf0cecf70e766cf256c87b","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Use one grammar for every governed active-index read: the exact empty document is `# Active Plan`, one blank line, `No active development items.`, and one trailing newline; the populated document uses the same title and blank line, the `id<TAB>path<TAB>status` header, one or more actual-tab rows, and one trailing newline.
  - Treat literal backslash-t characters as ordinary invalid text. Reject blank files, a header without rows, rows without the exact header, content before or after the selected representation, multiple empty markers, and an empty marker mixed with a header or row.
  - Validate row count, three-digit id, normalized active path, filename/id agreement, allowed status, duplicate id and path, referenced-file existence, manifest status, and the single in_progress rule before any mutation.
  - Do not auto-repair or partially parse an invalid document. Report the first concrete fault and leave the index, plans, archives, and checked index byte-identical.
  - Retain the current lifecycle lock and atomic replace or rollback behavior. A canonical writer receives only fully parsed rows and writes no output until the complete new state passes validation.
  - Cover root complete/finalize operations and generated create, activate, complete, finalize, and restructure consumers without widening the accepted grammar of checked.md or replanned.md.
  - Keep this plan independent of plans 275 and 277; policy routing and observed resource summaries do not repair the reproduced parser defect.
checked_summary_ja: 壊れた実行中プラン一覧を空として通さず、すべての更新前に同じ厳密な形式で検査する。

## Decisions

- The concrete target is the active-plan index reader and writer used by root checks and generated plan lifecycle commands.
- Preserve exactly one empty form and one actual-tab TSV form; reject all other nonempty text rather than recovering selected rows.
- Keep the index as the existing lifecycle record. Do not add a second index, migration file, or compatibility representation.
- Apply the strict parser before mutation and keep existing locks and rollback boundaries.

## Tasks

- [ ] Add failing root and generated fixtures for every malformed form and preservation case named in the completion conditions.
- [ ] Implement strict whole-document parsing and canonical serialization in the existing root and generated lifecycle paths.
- [ ] Route root completion and finalization through the same validated representation before either operation mutates a plan, index, or archive.
- [ ] Update root/generated policy and parity assertions for the exact grammar and fail-closed behavior.
- [ ] Run focused validation, obtain independent review, and run the unchanged authoritative suites once for an acceptable candidate.

## Validation Notes

- Planning baseline: `751b6b9d522ceaea727fd92be0ee81b816fac502` in `temp_project`.
- Owner direction: 「提案の方針でプランを docs/plan/backlog に作成せよ。」 This approves the selected design for backlog authoring; this turn does not activate or implement it.
- The reproduced defect used a disposable fixture and did not change repository files. Feasibility evidence is not a claim that future completion witnesses already pass.
- Plan 275 routes detailed policy and Plan 277 summarizes already-observed resources. Neither is a prerequisite for this deterministic parser correction.
- No performance, retry, or time saving is claimed. The future implementation must establish only the declared correctness and preservation behavior.
- Plan-authoring validation passed: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` exited 0. Smoke exercised generated-project cases; its optional GitHub Actions lint was skipped because `actionlint` was unavailable.
- Root admission, witness-digest, validation-command, context-path, and whitespace checks passed. These results validate this backlog document and the existing repository, not the future parser implementation.
