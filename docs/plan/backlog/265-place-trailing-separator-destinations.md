# Report a directory destination written with a trailing separator

status: backlog
primary_invariant: the focused checker places an operand inside a destination directory whether that directory is written with or without a trailing path separator, so no copy or install into the update source is admitted by the way its destination is spelled
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"At the commit that checked Plan 251, cp \"$root/AGENTS.md\" \"$tmp/update-source/\" returns zero findings while the identical mv form returns two, and install with the same destination also returns zero."}
  - {"kind":"reproduced_defect","evidence":"The same cp written with an explicit filename destination, cp \"$root/AGENTS.md\" \"$tmp/update-source/AGENTS.md\", returns two findings, so only the trailing-separator spelling is admitted."}
  - {"kind":"existing_mechanism","evidence":"The rename path already produces the inside pairs this plan needs; _helper_paths emits them for mv but not for a cp or install destination that ends in a path separator."}
completion_conditions:
  - A copy or install operation whose destination resolves to a directory written with a trailing path separator is placed inside that directory, so cp "$root/AGENTS.md" "$tmp/update-source/" reports the findings the equivalent mv already reports instead of zero.
  - Existing accepted operations keep their disposition: the committed fixture still passes --check, and a destination written without a trailing separator keeps the reading it already has.
completion_witness_map:
  - {"condition_sha256":"sha256:d0f4b5007f5b38acdcbd9d9c835d372b7500eda0158a2223b1d164d26b2dcdd7","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:6cfb62f66670a1fcd3f1f75167b75cb9c05174b21e8aa9f331ebb1bd3e5d51cb","witness":"python3 tests/test-copier-fixture-validator.py"}
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/09/01-15/251-place-fixture-words-and-alias-sources.md
  - docs/plan/checked/2026/08/16-31/248-bind-fixture-editing-to-the-inventory.md
  - tests/copier-update.sh
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Place a copy or install operand inside a destination directory written with a trailing path separator, and report the resulting write into the update source with the findings the equivalent rename already produces.
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/251-place-fixture-words-and-alias-sources.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - measure the change differentially against the predecessor commit and admit no fixture that was rejected before and is accepted after
  - keep every existing rejection test passing
checked_summary_ja: 宛先ディレクトリを末尾セパレータ付きで書いた場合もoperandをその中に配置し、update sourceへの書き込みを報告できるようにする。

## Decisions

- Treat the trailing separator as a spelling of the same directory, not as a different destination kind. The rename path already decides this correctly, so the fix belongs in the shared destination placement rather than in a new command-specific rule.
- Do not widen the reading of a destination that carries an unresolved expansion. This plan closes a spelling gap for destinations the model already resolves; an opaque destination stays a fail-closed finding.

## Tasks

- [ ] Reproduce the cp and install admissions read-only against the checked Plan 251 commit with `tests/copier-update.sh` left byte-identical, and record the finding counts before the change.
- [ ] Emit the inside pairs for a copy or install destination that resolves to a directory written with a trailing path separator, reusing the placement the rename path already performs.
- [ ] Add mutation coverage for the cp, install, and mv trailing-separator forms and for a destination written without the separator.
- [ ] Measure the change differentially against the predecessor commit and record that no previously rejected fixture became accepted.
- [ ] Complete one independent read-only review and focused validation with zero unresolved High or Medium findings.

## Validation Notes

- Pending. The admission was found while checking Plan 251 and was confirmed to predate it, so it is a pre-existing hole rather than a regression that plan introduced.
