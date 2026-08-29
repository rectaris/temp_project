# Publish Git-managed HTML reports for team sharing

status: checked
primary_invariant: a shared human report is published only into the project-owned Git-tracked path through an explicit human-committed command, and its freshness validator fails closed whenever the recorded source bytes, the published HTML, or the publication gates no longer hold
task_types:
  - planning_docs
  - security
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: ordinary
implementation_tier: 2
write_scope:
  - CHANGELOG.md
  - copier.yml
  - docs/plan/active/242-git-managed-shared-html.md
  - docs/plan/checked.md
  - docs/plan/plan.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
  - template/.project-agent-workflow/human-report.json.jinja
  - template/.project-agent-workflow/scripts/human-report.py
  - tests/assert-generated-semantics.py
  - tests/copier-update.sh
  - tests/fixtures/broad.answers.yml
  - tests/fixtures/copier-pairwise.tsv
  - tests/fixtures/docs.answers.yml
  - tests/fixtures/escaping.answers.yml
  - tests/fixtures/python.answers.yml
  - tests/fixtures/typescript.answers.yml
  - tests/smoke.sh
  - tests/test-human-report.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/plan/checked/2026/08/01-15/045-local-human-report-html.md
  - template/.project-agent-workflow/docs/agent/SPEC_HUMAN_REPORTING.md
  - template/.project-agent-workflow/scripts/human-report.py
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
focused_validation:
  - python3 tests/test-human-report.py
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-human-report.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Publish the reviewed structured source and its derived HTML only under the project-owned Git-tracked `docs/human-report/<report-id>/` path, and keep the structured source the reviewed artifact.
  - Bind regeneration, freshness, retention, removal, supersede, and merge-conflict behavior to an explicit command that never stages or commits, and fail closed when recorded source bytes, published HTML, or conflict markers show a stale or blocked report.
  - Fail publication closed on unreviewed content, raw logs, unredacted private data, secret-like material, unsafe source paths, scripts, external resources, and missing accessibility structure.
  - Keep Copier managing only the generator, policy, configuration, and validator, and reject any managed template or generated-inventory path that would own project report content.
  - Prove team access and stale-report detection in a generated-project fixture that commits a published report, reads it from a separate checkout, and fails the freshness validator after the source changes.
checked_summary_ja: チーム共有する HTML 報告を project 所有の Git 追跡先へ明示コマンドで公開し、鮮度検査と公開ゲートで失敗時に停止する仕組みを template に追加した。

## Decisions

- Store the shared report under the project-owned path `docs/human-report/<report-id>/`. `.agent-artifacts/human-reports/` is Git ignored and `.project-agent-workflow/` is Copier managed, so neither can own project report content.
- Review the Git-tracked structured source `report.json`. Treat `index.html` as a derived publication file bound to that source by a freshness check.
- Limit publishing to a repository file. CI artifacts and hosted static sites stay out of scope until a separate approved plan grants that authority.
- Regenerate through the explicit `publish` command. The command never stages and never commits; a human reviews, stages, and commits.
- Gate publication on the new `human_report_shared_mode` Copier question. `disabled` is the default and refuses publication. `explicit_publish` allows the human-committed path. This question is the exact explicit project configuration that a later approved plan would extend to enable automatic commits; automatic commits remain unimplemented.
- Record `generator_version`, `generated_at`, `source_commit`, and every source path with its SHA-256 in both the published structured source and the published HTML.
- Fail `verify-shared` closed when a recorded source file is missing, its current bytes hash differently, the published HTML no longer equals a deterministic re-render of the recorded document, a publication gate no longer holds, or a Git merge-conflict marker is present.
- Update a published report only through an explicit `--supersede` flag on `publish`, and remove one only through an explicit human removal commit. Never prune automatically and never overwrite an unresolved merge conflict.
- Run the publication gates over both the structured source and the rendered HTML. Parse the rendered HTML with the standard library and reject scripts, event-handler attributes, external or scheme-bearing references, and a missing document language, top-level heading, embedded style, scoped table header, or print layout.
- Keep `docs/human-report/` outside every Copier source and generated inventory, and enforce that boundary with a deterministic checker.
- Prove team access and stale detection in the generated TypeScript smoke fixture, which publishes, commits, clones to a separate checkout, reads the published files there, then changes the source and requires the freshness validator to fail.

## Tasks

- [x] Resolve the storage, publication, ownership, and retention decisions.
- [x] Define the security and accessibility acceptance gates.
- [x] Update the write scope and validation list after the decisions are accepted.
- [x] Obtain explicit human approval before promotion to active implementation.
- [x] Add the `human_report_shared_mode` Copier question, generated configuration, and inventory entries.
- [x] Add `publish` and `verify-shared` to the generated human report CLI with provenance, gates, and freshness checks.
- [x] Enforce the Copier ownership boundary for `docs/human-report/`.
- [x] Update the generated human reporting specification.
- [x] Add focused tests and the generated-project team-access and stale-detection fixture.
- [x] Run required validation and archive this plan.

## Validation Notes

- `python3 scripts/check-copier-template.py` passed, including the new
  `require_shared_human_report_boundary` check that keeps every template and
  generated inventory path outside `docs/human-report/`.
- `python3 tests/test-human-report.py` passed with 10 tests, covering shared
  publication, the disabled shared mode, supersede refusal, and stale detection.
- `scripts/lint-project-workflow.sh` passed.
- `tests/smoke.sh` passed, including `run_shared_human_report_smoke`, which
  publishes a report in a generated project, proves the published files are not
  Git ignored, clones the project, verifies the report from the clone, and then
  requires `verify-shared` to reject a changed source.
- `python3 scripts/validate-changes.py --all` passed.
- `tests/copier-update.sh` reaches the same pre-existing failure as clean
  `e2529bb` (`plan restructuring failed: successors[0] requires
  validation_witness_schema: 1`). The three `validate_common_lane` calls that run
  before that point pass, so an updated project records
  `human_report_shared_mode: disabled` and gains no template-owned
  `docs/human-report/` directory.
