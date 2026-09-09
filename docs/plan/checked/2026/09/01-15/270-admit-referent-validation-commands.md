# Admit the existing referent and hook test commands in root plans

status: checked
primary_invariant: root plans can invoke the two existing fixed semantic test entrypoints without permitting arguments or shell composition
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
review_class: B
human_design_required: no
human_approval_status: approved
plan_purpose: implementation
task_types:
  - template_workflow
  - planning_docs
  - security
  - referent_first
feasibility_evidence:
  - {"kind": "reproduced_defect", "evidence": "Schema-4 reconstruction of stopped Plan269 refuses its inherited python3 tests/test-referent-contract.py command because the root PYTHON_SCRIPT_ARGUMENTS table omits that existing script and tests/test-hooks.py."}
completion_conditions:
  - Both python3 tests/test-referent-contract.py and python3 tests/test-hooks.py pass root command validation with no arguments, while extra arguments and shell composition remain rejected.
completion_witness_map:
  - {"condition_sha256": "sha256:3b3819957bb2ceb525077ed5e924f118925e3a0c399bae9ca477b44da4804756", "witness": "python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/plan_validation_commands.py
  - tests/validation_tools/plan.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - references/orchestration.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_REFERENT_FIRST.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/plan_validation_commands.py --self-test
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The root plan validator accepts exactly the existing no-argument referent-contract and hook test commands while preserving all prior accepted commands and argument or shell rejection rules.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256": "sha256:45ae7e9989db5e1976ea64651684d52442267bef631c2ecd3a7ff1064529548d", "stage": "focused", "witness": "python3 tests/test-validation-tools.py"}
integration_gates:
  - Use bounded parent implementation because this change touches validation authority; require independent read-only review before authoritative validation.
  - The two root repository tests are not installed in generated projects, so do not add nonexistent root test paths to the generated validator.
  - Keep stopped Plan269 and its unaccepted implementation unchanged until this prerequisite is checked.
checked_summary_ja: 計画に記載済みの用語記録と hook のテストを、引数なしの固定コマンドとして許可する。

## Decisions

- The owner instructed 「作業を続けよ。」; this bounded prerequisite makes the inherited validation commands executable through reconstruction without deleting or weakening them.
- Add only two exact root Python entrypoints with the empty argument tuple. Preserve the parser, shell rejection, generated command table, and all other entries.
- Root-only placement is intentional: neither test entrypoint is installed in generated projects. The generated validator has a distinct table and needs no nonexistent test path.

## Tasks

- [x] Add the two fixed root command entries and positive and negative regressions.
- [x] Obtain independent review and pass focused and authoritative validation.
- [x] Commit and archive this prerequisite, then reconstruct Plan269 with its full original validation list.

## Validation Notes

- Focused validation passed: 79 validation-tool tests, command-parser self-test, and git diff --check.
- Independent change review found no High, Medium, or Low findings; the parent verified the exact two-file patch digest.
- scripts/lint-project-workflow.sh passed in a separate validation copy. Its first sandbox launch could not create the migration-test Unix socket; the owner-approved host retry passed unchanged.
- REQUIRE_COPIER=1 tests/smoke.sh passed in a separate validation copy with the installed Copier environment.
- Product commit: 0b53e5fd82717d65b839d9c70f7da3e38cf006ff.
- Root-only placement is intentional because generated projects do not contain these two root repository tests.
