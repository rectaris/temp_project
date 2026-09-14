# Restore shelved_reason and shelved_at to the manifest parser the plan lint reads

status: checked
implementation_mode: parent_direct
primary_invariant: Every manifest field the plan lint reads through planlib is a field planlib preserves.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"parse_manifest_text returns an empty shelved_reason and shelved_at for a manifest that declares both, because SCALAR_KEYS omits them.","kind":"reproduced_defect"}
  - {"evidence":"SCALAR_KEYS already carries every other scalar field the lint reads, and restructure-plan.py keeps its own permissive parser that preserves both fields.","kind":"existing_mechanism"}
completion_conditions:
  - A shelved plan written by shelve-plan.sh passes the generated plan lint.
  - A scalar or list manifest field that the generated lint reads through planlib but that planlib does not preserve fails a test.
completion_witness_map:
  - {"condition_sha256":"sha256:a597969ffc7aa3d10a485a8393208213e4db4b572619646a14e484cce16c5066","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:f5cd3cd9badc6bfa03d766a60cc5361fd5336f5142da302e7c5760b80c904e37","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/.project-agent-workflow/scripts/lint-plan-docs.py
  - template/.project-agent-workflow/scripts/shelve-plan.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - python3 tests/test-validation-tools.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The generated plan lint accepts a shelved plan that carries shelved_reason and shelved_at.
  - The generated-project suite keeps passing with the shelved lifecycle restored.
  - A test fails when the generated lint reads a manifest field through planlib that planlib drops.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:af482485f6929736c53f08ef01fa4fd13f5174ae7a4062232167a606d4fa663e","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:4eaf0ab37f3795f608b0cd5a675db937bf86725cdaf53d8f05c687a41b79e235","authoritative_only_reason":"The generated-project suite exists only inside the Copier fixture that tests/smoke.sh builds, so no narrower command runs it.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:0cb9fa17fd397a2a81d2c0f69f80af6d7ad9990f3621478fefc1193e385e375c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 計画の見送り理由と見送り日を、検証が読む解析器に復帰させる。

## Decisions

- Add shelved_reason and shelved_at to SCALAR_KEYS rather than relax the lint. The lint already states the requirement the shelve command writes, so the parser is the side that is wrong.
- Derive the guard from the lint source instead of restating the field list. A test that reads planlib.manifest_scalar and planlib.manifest_list call sites in lint-plan-docs.py and asserts each literal key is in SCALAR_KEYS or LIST_KEYS cannot fall out of date the way a second hand-written list would.
- Leave restructure-plan.py's own permissive parser unchanged. It already preserves both fields, and merging the two parsers is a separate change with a wider blast radius.
- Carry this as Tier 2 because it restores a plan lifecycle state rather than adjusting a single covered file.

## Tasks

- [x] Add shelved_reason and shelved_at to SCALAR_KEYS in the generated planlib.
- [x] Add a test that a shelved plan carrying both fields passes the generated plan lint.
- [x] Add a test that derives the lint's planlib field reads from its source and asserts each key is preserved by the parser.
- [x] Run the declared validation commands.

## Validation Notes

- Implementation: parent-direct in the task-bound worktree for plan 341. The plan's whole write scope is `template/.project-agent-workflow/scripts/planlib.py` and `tests/validation_tools/plan.py`, which the sandboxed writable runner refuses as validation-authority paths, so no delegated worker was started and no execution ledger run was opened.
- Defect reproduced before the change: a plan shelved by the generated `shelve-plan.sh` failed the generated lint with `status: shelved requires shelved_reason`, because `parse_manifest_text` preserves only keys listed in `SCALAR_KEYS` or `LIST_KEYS`. Adding both fields to `SCALAR_KEYS` makes the same fixture lint clean.
- Guard: `generated_lint_manifest_reads` derives the lint's manifest reads from `lint-plan-docs.py` itself, covering `planlib.manifest_scalar`, `manifest_joined`, and `manifest_list` calls in both qualified and bare form, plus string-literal subscripts of the names that function binds to a parsed manifest. Both derived sets must be non-empty, so neither half can pass vacuously. Mutation checks: removing `shelved_reason` or `shelved_at` from `SCALAR_KEYS` fails all three new tests, and removing `integration_gates` from `LIST_KEYS` fails the two guard tests.
- Focused validation: `python3 tests/test-validation-tools.py` — 319 tests, OK. Supporting parent check: `python3 scripts/check-copier-template.py` — passed.
- Authoritative validation ran once after the accepted review state: `scripts/lint-project-workflow.sh` exit 0, `tests/smoke.sh` exit 0.
- Independent review: two rounds by a read-only `code-review` helper, which had no write scope and no repository effect; the main session judged every finding and kept acceptance authority. Round 1 raised three Medium findings: the shelve fixture depended on the temporary directory not lying inside a Git repository, the AST guard ignored any read written as a bare imported call and its list half was vacuous, and the plan's `authoritative_only_reason` claimed `tests/smoke.sh` exercises the shelve lifecycle. All three were remediated. Round 2 raised one Medium finding: the parsed-manifest names were bound module-wide, so a future literal subscript of the unrelated `values` dict in `render_admission_block` would be misread as a manifest field.
- Unreviewed at acceptance: the round 2 remediation itself, which scopes each parsed-manifest binding to its own function and also drops `GIT_DIR` and `GIT_WORK_TREE` from the fixture's environment. It is the reviewer's own prescribed fix, the epoch's two reviews were spent, and it was verified by re-running the reviewer's reproduction (an unrelated literal subscript in `render_admission_block` no longer fails the guard) together with the mutation checks above.
- Round 1 finding 3 is recorded rather than absorbed: `tests/smoke.sh` never invokes `shelve-plan.sh`. The only executable coverage of the shelve lifecycle in this repository is the new unit test, and smoke stays the authoritative witness for the generated-project suite alone.
