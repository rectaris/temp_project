# Hold every project that keeps an active plan index to the same grammar, and say when a document has not adopted that grammar at all

status: checked
primary_invariant: Both enforcing commands reach the same conclusion about one docs/plan/plan.md, and a document that does not open with the index title is reported as unadopted rather than as a first-line defect.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Verifying supportcard-status against v1.4.5 returned rejected with change_validation_failed. validate-changes.py stopped before reading a single changed file, so all fifteen checks it would otherwise select, including the static secret scan, ran zero times.","kind":"reproduced_defect"}
  - {"evidence":"validate-changes.py treats docs/plan/active/ as proof the canonical grammar is in use, while check-agent-completion.sh parses whenever docs/plan/plan.md exists. On one project-owned Japanese index the two commands reach different conclusions about the same file.","kind":"reproduced_defect"}
  - {"evidence":"check-copier-template.py already requires one byte-identical active plan index grammar block across thirteen enforcing commands, so a message added inside that block reaches every command without a second definition.","kind":"existing_mechanism"}
completion_conditions:
  - A docs/plan/plan.md that does not open with the index title is reported as not having adopted the format, with the whole required document stated and the owner decision named, rather than as a defect in its first line.
  - The change validator and the completion gate accept the same documents and reject the same documents, so neither treats an index the other ignores.
  - The plan lint and plan formatter are selected when docs/plan/plan.md is kept and not selected when it is absent, without inferring adoption from docs/plan/active/ or from the document's own contents.
completion_witness_map:
  - {"condition_sha256":"sha256:c3193f618d0b63d657c631f8624c88316d3a4c4d1f7f70c49e772823005e0d95","witness":"python3 -m unittest tests.validation_tools.changes"}
  - {"condition_sha256":"sha256:365b9611b59e7ddc070ed114a364321906ecfe6d2ef0ab4529e06a0e0b11471d","witness":"python3 -m unittest tests.validation_tools.changes"}
  - {"condition_sha256":"sha256:4f3198c64846084cc2b2d0168d74c11b4c6f6b2746ebf379ae961bdef5893ee4","witness":"python3 -m unittest tests.validation_tools.changes"}
write_scope:
  - scripts/validate-changes.py
  - template/.project-agent-workflow/scripts/validate-changes.py
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - scripts/complete-plan.sh
  - scripts/finalize-active-plan.sh
  - scripts/restructure-plan.py
  - template/.project-agent-workflow/scripts/restructure-plan.py
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - template/.project-agent-workflow/scripts/planlib.py
  - tests/validation_tools/changes.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/check-copier-template.py
  - docs/downstream-baselines.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 -m unittest tests.validation_tools.changes
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Every project that keeps an active plan index is judged by one grammar through both enforcing commands, and a project that keeps an unadopted index learns that adopting the grammar replaces the whole document.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6e576a18cd173192af01977dd61e5b569c5c22dfda3b539fdb1db82e032d3d32","stage":"focused","witness":"python3 -m unittest tests.validation_tools.changes"}
checked_summary_ja: 能動計画索引を持つプロジェクトを同じ文法で一様に判定し、その文法をまだ採っていない文書にはそう告げる

## Decisions

- Judge every project that keeps docs/plan/plan.md by the same grammar rather than inferring adoption, because the owner has decided that docs/plan/active/ is always present and docs/plan/plan.md is always the canonical English index, which leaves nothing for an inference to distinguish.
- Separate the unadopted document from the malformed one by the title line alone, because a document that does not open with the title is not a damaged index but a different document, and the two need different next actions.
- State in the diagnosis that adopting the format replaces the whole document and that project-owned content needs its owner's decision, because the previous message let an agent edit one line at a time and discard project-owned prose as a formatting repair.
- Put the message inside the shared grammar block, because the existing template check already holds that block byte-identical across thirteen commands, so both enforcing commands report one text without a second definition.

## Tasks

- [x] Name the unadopted document distinctly inside the shared active plan index grammar and propagate the block to every enforcing command.
- [x] Judge the index by whether the project keeps it, removing the inference from docs/plan/active/ and from the document's contents.
- [x] Cover the unadopted diagnosis, the selection rule, and the agreement between the two enforcing commands.

## Validation Notes

- `python3 -m unittest tests.validation_tools.changes` (26 tests) and
  `python3 -m unittest tests.validation_tools.plan` (79 tests) pass.
- `scripts/lint-project-workflow.sh` passes, including
  `scripts/check-copier-template.py`, which holds the shared grammar block
  byte-identical across the 13 enforcing files.
- Reproduced the reported defect against a copy of the served project's
  document: the gate now names the document unadopted and no longer prints the
  contradictory instruction to rewrite it.
- One independent read-only review round was used. It returned three Medium
  findings, all accepted and fixed: the trailing-newline rule ran ahead of the
  title rule, the completion gate printed a rewrite instruction next to the
  owner warning, and the agreement test read acceptance from stderr text rather
  than exit status. Those fixes were not independently re-reviewed; the main
  session accepted them on the strength of the tests above.
