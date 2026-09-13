# Admit registered pre-boundary archived contract sources

status: checked
primary_invariant: Canonical stopping stays required for every new restructuring and every unregistered archived contract; only an explicitly registered, boundary-committed, byte-bound historical contract source is verified against its recorded status instead.
task_types:
  - plan_lifecycle
  - validation_tooling
  - planning_docs
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"load_pre_boundary_reconciliations already implements a write-once, boundary-bound historical registry with ancestry, single-commit history, and exact blob-at-boundary checks, and reconciled_pre_boundary_archive already gates exactly the checks it closes.","kind":"existing_mechanism"}
  - {"evidence":"verify_repository_contracts already reaches the archived contract source through validate_replanned_successor and its own contract walk, so the relaxation has exactly two schema-1/2 assertion sites plus the expected-status comparisons their callers hold.","kind":"existing_mechanism"}
  - {"evidence":"blob_bytes_at_commit, commit_is_ancestor_of_head, committed_file_bytes, read_regular_file and reject_symlink_ancestors already supply every primitive the new registry needs, and tests/test-plan-restructure.py already builds synthetic repositories for restructuring regressions.","kind":"existing_mechanism"}
completion_conditions:
  - The pre-boundary contract-source registry is admitted only when it is write-once, names a boundary commit that is an ancestor of HEAD, and binds every listed contract and archive to the exact bytes already committed at that boundary.
  - A registered archived contract source is verified against its recorded active status instead of the canonical stopped status, while its path, digest, acceptance, lineage, preservation, archive state and committed-byte immutability are still verified.
  - An unregistered archived contract source still requires canonical stopping at every verification site, and contract creation still refuses a source that is not canonically stopped.
  - The root and template copies of the restructuring script and the plan workflow specification stay aligned, and the specification describes the registry as a closed historical reconciliation that admits nothing else.
completion_witness_map:
  - {"condition_sha256":"sha256:ce241cf15b0c70a360f15a0dfb533457d84486a54bd7b79723cef76af7f9cde8","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:63d88596e02d2a385d5ba19f78bddc782273f5bc31263ad38f494a29d3725435","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:3206c052a052e4d93b4065675b79904d45462d7fa74a4ade5f30677baffdc961","witness":"python3 tests/test-plan-restructure.py"}
  - {"condition_sha256":"sha256:e78d97bf05eaddf543a20d3adafbfe61a2d5803de0c44a67d4bb88f225d74f87","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - tests/test-plan-restructure.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - references/validation.md
  - docs/plan/checked/2026/08/16-31/240-reconcile-pre-boundary-lifecycle-and-replanned-lineage.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - references/validation.md
  - references/orchestration.md
focused_validation:
  - python3 tests/test-plan-restructure.py
  - python3 scripts/check-copier-template.py
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The repository admits an explicitly registered, boundary-committed archived contract source that was never canonically stopped, and rejects every registry that is not write-once, not boundary-committed, or not byte-bound, without weakening canonical stopping for unregistered contracts or for new restructuring.
  - The root and template copies of the changed script and specification remain aligned and document the registry as a bounded historical reconciliation that must not be used for new work.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:a8806b2ae598ac82a5d634b17198efc8780aec482d7ce039c2a96cf78f2f81f9","stage":"focused","witness":"python3 tests/test-plan-restructure.py"}
  - {"acceptance_sha256":"sha256:8811d506eb26a74309c0b58db61d13b44df7ed8ed1d03353033c24ecdb25eaa6","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: 正規停止前に確定した過去の再計画契約を、限定されたレジストリで受け入れる

## Decisions

- The referent is one recorded object: the source field of an already archived, immutable replan contract whose recorded plan text was never marked replan_required. It is not a plan, not a lifecycle status, and not a class of template versions.
- The owner instruction is to fix the template rather than the affected project. A downstream project generated from v1.4.1 cannot satisfy the retroactive canonical-stop assertion, because its archived contract and archive bytes are immutable and an independently recorded parent contract binds the same plan text.
- Reject the discriminator schema_version == 1. Independent review established that the v1.4.1 writer already required status: replan_required, so an unstopped schema-1 source is an anomaly rather than a vintage, and a version-shaped exemption would open a permanent lane for every project.
- Follow the existing pre-boundary lifecycle reconciliation registry instead: a project-owned, hand-written, write-once JSON record that names each anomalous contract exactly, binds its bytes, and proves it already existed at a named ancestor boundary commit. A defect introduced after the boundary can never be admitted.
- Relax only the canonical-stop assertion and the expected-status comparison that follows it. Keep source path, plan digest, acceptance records, inherited acceptance digests, preservation scope, projection, archive status and lineage, and committed-byte immutability exactly as they are.
- Do not add the reviewer's proposed general binding of source.content to the git blob at source.head. Contract creation reads the working tree and dirty_product_paths ignores docs/plan, so an honest historical contract may legitimately record a stop that was never committed separately; adding that check would break existing projects and is a separate decision.
- Leave creation-time canonical stopping untouched, so the registry can never authorize a new restructuring.

## Tasks

- [x] Add the registry path constant and a loader that reads docs/plan/replanned/baselines/pre-boundary-contract-sources-v1.json, mirroring load_pre_boundary_reconciliations: reject a symlink, require schema_version 1, a 40-hex boundary_commit that is an ancestor of HEAD, a non-empty entry list, live bytes equal to committed bytes, and exactly one commit in history.
- [x] Validate each entry as an exact object binding contract_path, contract_digest, archive_path, archive_digest, source_status and reason. Require matching plan ids and basenames, live bytes matching both digests, both blobs byte-identical at the boundary commit, a non-blank reason, a source_status in ACTIVE_PLAN_STATUSES that is not replan_required, and a recorded source manifest that carries neither replan_reason_codes nor a stale completion_deferred_reason.
- [x] Add one predicate that resolves a registered contract to its recorded status, and apply it where validate_replanned_successor asserts canonical stopping and where verify_repository_contracts asserts it on its own contract walk. Return the effective status from validate_replanned_successor so both callers stop hard-coding replan_required.
- [x] Leave every other canonical-stop call site unchanged, including contract creation, live successor lifecycle evolution, and the schema-3 and schema-4 source assertions.
- [x] Extend tests/test-plan-restructure.py with regressions that admit a registered anomalous contract, reject an unregistered one, reject a registry whose bytes drift from the boundary commit, reject a registry rewritten after its first commit, reject an entry whose recorded source is already canonically stopped or carries replan_reason_codes, and confirm contract creation still refuses an unstopped source.
- [x] Document the registry in the Pre-Boundary Lifecycle Reconciliation area of the plan workflow specification, stating that it closes named historical records only, weakens no other rule, and must not be used for new work.
- [x] Mirror the script and specification changes into template/.project-agent-workflow/ in the same change and confirm alignment with scripts/check-copier-template.py.
- [x] Have an independent read-only reviewer check the diff against the invariant before acceptance, then run the authoritative validation suite once and commit the accepted change.

## Validation Notes

- Independent review established that the v1.4.1 restructuring writer already required status: replan_required, so the observed record is an anomaly rather than pre-enforcement history. The registry is therefore scoped to named records, not to a template version.
- The focused suite proves the registry contract and the two relaxed assertion sites. It does not prove that any particular downstream project is reconcilable; that remains a separate project-owned judgement.
- Independent review of the diff returned three findings, all accepted and fixed in the main session. Two were real weakenings: the registry read replan_reason_codes through items() and completion_deferred_reason through scalar(), so an inline-list reason code and a block-shaped carryover both bypassed the stop-marker gate that the replaced assertion had caught. Both now test key presence, and one regression per shape pins the behaviour.
- The third finding was untraced coverage of the successor route. The added nested regression restructures a successor a second time and registers the downstream contract, which exercises the relaxed assertion inside validate_replanned_successor and the effective status both callers now consume.
- While writing that regression the same-plan check proved to be bound to the contract file name, which is only a naming convention. It now compares the archive stem with the stem of the source path recorded inside the contract, which is the property the check was meant to assert.
- Authoritative run: python3 scripts/validate-changes.py --all, scripts/lint-project-workflow.sh and tests/smoke.sh all exit 0, with 189 focused restructuring tests passing and the template mirror byte-identical.
