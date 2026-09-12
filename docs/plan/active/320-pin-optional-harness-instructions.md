# Pin optional instruction revisions and retain a measured adoption path

status: replan_required
replan_reason_codes:
  - scope_drift
primary_invariant: Selecting an optional instruction revision preserves governing requirements and project-owned selection bytes, and never silently activates an unmeasured or changed revision.
task_types:
  - template_workflow
  - test_coverage
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"scripts/update_agent_model_profiles.py and tests/test-agent-model-profiles.py already preserve project-owned model/reasoning values through fill-only updates; keep that mechanism and use a separate optional instruction selection file.","kind":"existing_mechanism"}
  - {"evidence":"template/.project-agent-workflow/ownership.yaml separates managed files from seeded project-owned files, and tests/copier-update.sh exercises preservation and conflict stopping.","kind":"existing_mechanism"}
  - {"evidence":"The preceding local-comparison implementation supplies explicit instruction and evidence digests; this plan consumes its published output contract without changing its comparison or acceptance rules.","kind":"existing_mechanism"}
completion_conditions:
  - Explicit selection resolves only an exact optional instruction revision and content digest; missing, changed, retired or unknown selections are reported without fallback, rewriting project choices or loading all model variants.
  - Catalog entries distinguish protected governing sources from optional supplemental advice and record rationale, applicability, failure-case references and review evidence; selection cannot disable governing rules or alter runtime model settings.
  - The command renders only selected supplemental advice with its identity, and checks an adoption or rollback record against the exact published comparison contract without changing repository state or claiming runtime activation.
  - Freshly generated projects use an empty optional selection, while update fixtures preserve a nondefault project selection, local supplemental text and prior revision references or stop on conflicts without deleting them.
completion_witness_map:
  - {"condition_sha256":"sha256:0b0bf96db017875020011f8b4f1976ae0d1e8b6c5cc3b824127a07a998fafb93","witness":"python3 tests/test-harness-profiles.py"}
  - {"condition_sha256":"sha256:96579be78dcb145c8ae7df297fbb185093b06558436225d6c427aca83afd44bb","witness":"python3 tests/test-harness-profiles.py"}
  - {"condition_sha256":"sha256:9b75c3e2340f144001eb10425299c0b6e72a6634e9b31bf05ddb8df1e6f47664","witness":"python3 tests/test-harness-profiles.py"}
  - {"condition_sha256":"sha256:3a5c4ced04ac1f8fa8cb0f72d4543ee9613907b9384f255c72842d583456554a","witness":"python3 tests/test-harness-profiles.py --copier-preservation"}
write_scope:
  - scripts/check-harness-profile.py
  - template/.project-agent-workflow/scripts/check-harness-profile.py
  - docs/agent/harness-profile.json
  - template/docs/agent/harness-profile.json.jinja
  - docs/agent/harness-instructions.json
  - template/.project-agent-workflow/docs/agent/harness-instructions.json
  - docs/agent/SPEC_HARNESS_PROFILES.md
  - template/.project-agent-workflow/docs/agent/SPEC_HARNESS_PROFILES.md
  - tests/test-harness-profiles.py
  - tests/fixtures/harness-profiles/cases.json
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - template/.project-agent-workflow/ownership.yaml
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/update_agent_model_profiles.py
  - tests/test-agent-model-profiles.py
  - template/.project-agent-workflow/scripts/summarize-agent-run.py
  - copier.yml
  - docs/plan/checked/2026/09/01-15/302-complete-routed-agent-policy.md
  - docs/plan/checked/2026/09/01-15/319-compare-harness-runs-locally.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - references/validation.md
focused_validation:
  - python3 tests/test-harness-profiles.py
  - python3 tests/test-harness-profiles.py --copier-preservation
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Users can check and render an explicitly pinned optional instruction revision, retain its failure rationale and evaluation links, and assess adoption or rollback without changing governing rules or silently choosing a new model.
  - Generated projects receive aligned profile tooling while existing products, policy, configuration and selected instruction revisions survive supported copy/update paths.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:834c5a07b47a3403ef74536faa87a302745fa7727614212a649466a3fd98a370","stage":"focused","witness":"python3 tests/test-harness-profiles.py"}
  - {"acceptance_sha256":"sha256:0dc0a3f9efccd3cdcabef1de661496138a920902a05f2e7183104d4dabd4d896","stage":"focused","witness":"python3 tests/test-harness-profiles.py --copier-preservation"}
integration_gates:
  - docs/plan/active/319-compare-harness-runs-locally.md must be checked and published before activation; consume its unchanged comparison contract and evidence semantics.
checked_summary_ja: 補助指示を版指定で選び、比較記録を確認して採用または以前の版への復帰を判断できるようにする。

## Decisions

- Implement only after the comparison plan is checked and published. Resolve its actual checked archive and final SPEC_HARNESS_EVALUATION.md before activation. Keep this plan backlog until then; use the existing checked authoring/promotion workflow rather than editing lifecycle fields by hand.
- Keep optional instruction selection separate from .codex/agents/*.toml and from allowed writable-runner model routing. Do not change model identifiers, budgets, permissions, required tests, lifecycle state machines, AGENTS.md precedence or owner approval rules.
- A catalog entry identifies either an exact governing source retained unchanged or an optional supplemental instruction revision by a stable id, revision and content digest. Include applicability by concrete task and optional exact model selector, introduction reason, linked failure case and review evidence. Unclassified existing instructions remain governing for this mechanism; the tool never classifies prose automatically.
- Seed a small reviewed inventory of existing authority/validation sources and auxiliary instruction locations, with the locations treated as governing unless explicitly extracted and approved for optional use. Do not claim the inventory is exhaustive or that a digest establishes semantic nonconflict. Give operators a bounded inventory worksheet for remaining instructions.
- The project-owned selection names explicit catalog/revision/digest values and project-local supplemental assets, with empty optional selection as the compatibility default. No latest alias, family-based guess, automatic downgrade, model-specific full-copy stack, network resolution or runtime discovery. Only selected entries appear in rendered output.
- Provide check and render modes that read explicit files and emit bounded stdout records/text. Rendering supplies supplemental task instructions for an operator-controlled invocation; it does not remove already loaded AGENTS.md/skills, supersede system/developer instructions or prove the host loaded its output. Explain this limit in every rendered bundle manifest.
- Keep the shipped default behavior unchanged and ship no claim of Astra-specific superiority. Use clearly synthetic candidate text only in tests. An operator may add an optional revision using ordinary reviewed Git changes, evaluate it with the preceding tool, and select it explicitly. Moving an existing governing instruction into optional scope requires a separately accepted policy change.
- An adoption record binds the exact prior and proposed selection digests, comparison input/report/evidence digests and operator decision; check recomputes the comparison with the existing command rather than trusting a passed string. It is advice to the owner, not authorization or automatic promotion. Preserve an explicit keep-current outcome.
- A rollback record identifies the prior exact selection and revision bytes. Never substitute another revision if the prior one is absent. Permit an operator to return to a previously recorded compatible revision without claiming new performance evidence; report changed governing inputs as requiring reassessment. No command writes the selection file.
- Retiring an optional revision retains its introduction reason, failure case and historical references. Mark it unavailable for new adoption; retain exact archived content for explicit rollback of existing records. Existing selections of a retired revision report the retirement and remain reproducible. A model release does not retire anything automatically.
- Seed project-owned selection only on fresh generation using the existing ownership/update preservation mechanism. Keep shared catalog defaults managed and project-local assets project-owned. Refuse conflicts or unresolved removals; do not silently recreate a missing selected revision or overwrite an existing selection. Retain prior referenced bytes when catalog maintenance removes an entry from new-adoption choices.
- Keep shared catalog/spec behavior aligned between root and template after the established path rewrite. Add a narrow harness-profile route and mechanical alignment/installation checks. Reuse the existing Copier updater and comparison verifier; do not build another update engine, model runner or mandatory every-task preflight.

## Tasks

- [ ] Read the completed comparison contract and preserve its evidence semantics; define bounded catalog, project selection, adoption and rollback record shapes.
- [ ] Implement check/render in the template-owned command with a thin root wrapper, an unchanged default, explicit selected revisions and protected-source metadata.
- [ ] Document the instruction inventory, controlled trial, keep-current, adoption, retirement and rollback operations, including runtime-loading limits and the separate authority needed to change governing policy.
- [ ] Add positive and negative fixtures for unknown revisions, digest drift, protected-source selection, fake comparison success, changed policy during rollback, retired revisions and unobserved activation.
- [ ] Register ownership, inventory and policy alignment; exercise fresh generation and updates preserving nondefault project choices, local assets and exact prior revisions.
- [ ] Review the exact diff and invariant, obtain required independent review, run focused checks and the unchanged authoritative suite, commit and publish without a remote push or a model-performance claim.

## Validation Notes

- Owner instruction: 提案の方針でプランを作成せよ。 This authorizes these plans; this authoring task does not execute their implementation or call models.
- Reuse the accepted direction: preserve project requirements and authority, compare bounded instruction changes, retain failure cases, and pin adoption with a rollback path.
- Implementation validation is pending. Synthetic fixtures establish tool behavior only; they are not observed model performance.
- Use bounded parent implementation with the existing external execution ledger and independent read-only review because specification and validation registration paths are part of this scope. Preserve all existing execution and review budgets.
