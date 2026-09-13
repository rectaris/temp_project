# Restore shelved_reason and shelved_at to the manifest parser the plan lint reads

status: backlog
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
  - {"acceptance_sha256":"sha256:4eaf0ab37f3795f608b0cd5a675db937bf86725cdaf53d8f05c687a41b79e235","authoritative_only_reason":"The shelve lifecycle runs through the generated project fixture, which no narrower command builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:0cb9fa17fd397a2a81d2c0f69f80af6d7ad9990f3621478fefc1193e385e375c","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: 計画の見送り理由と見送り日を、検証が読む解析器に復帰させる。

## Decisions

- Add shelved_reason and shelved_at to SCALAR_KEYS rather than relax the lint. The lint already states the requirement the shelve command writes, so the parser is the side that is wrong.
- Derive the guard from the lint source instead of restating the field list. A test that reads planlib.manifest_scalar and planlib.manifest_list call sites in lint-plan-docs.py and asserts each literal key is in SCALAR_KEYS or LIST_KEYS cannot fall out of date the way a second hand-written list would.
- Leave restructure-plan.py's own permissive parser unchanged. It already preserves both fields, and merging the two parsers is a separate change with a wider blast radius.
- Carry this as Tier 2 because it restores a plan lifecycle state rather than adjusting a single covered file.

## Tasks

- [ ] Add shelved_reason and shelved_at to SCALAR_KEYS in the generated planlib.
- [ ] Add a test that a shelved plan carrying both fields passes the generated plan lint.
- [ ] Add a test that derives the lint's planlib field reads from its source and asserts each key is preserved by the parser.
- [ ] Run the declared validation commands.

## Validation Notes
