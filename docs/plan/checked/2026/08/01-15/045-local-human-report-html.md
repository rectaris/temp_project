# Add agent-selected local HTML reports

status: checked
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - copier.yml
  - docs/agent/
  - docs/plan/
  - scripts/
  - template/
  - tests/
context_files:
  - .agent-artifacts/referent-contracts/local-human-report-html/contract.json
required_specs:
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Let generated-project agents submit bounded structured report data and receive a deterministic generate-or-skip decision with reasons.
  - Render selected reports as standalone escaped HTML only below `.agent-artifacts/human-reports/`, without external assets or Git-tracked output.
  - Keep durable Markdown plans and repository evidence authoritative and expose source provenance in each generated report.
  - Route generated-project user communication through the policy and provide a Copier mode that can disable the behavior.
  - Add deterministic unit, generated-project smoke, security, and Copier-update-safe coverage.
  - Create a separate backlog plan for Git-managed team-shared HTML without implementing that storage path now.
checked_summary_ja: 開発者向け報告を構造化入力から判定し、必要な場合だけ Git 対象外の単一 HTML としてローカル生成できる template 機能を追加した。

## Decisions

- A human report is a developer-facing progress or decision artifact assembled from repository evidence.
- agent_select_local is a generated-project mode that lets the agent decide whether to create an ignored local HTML rendering.
- A local HTML report is a standalone escaped HTML file written only below .agent-artifacts/human-reports/ and excluded from Git.
- A shared HTML report is an HTML file intentionally stored in a Git-tracked project-owned path for team access.
  It remains outside this implementation.
- Use agent-supplied semantic features with deterministic assessment gates instead of free-form format selection or word-count heuristics.
- Use a structured JSON report contract and a standard-library renderer instead of accepting raw HTML.

## Tasks

- [x] Add generated policy, routing, and Copier configuration for local human reports.
- [x] Add deterministic assessment and HTML rendering scripts with bounded output handling.
- [x] Add focused tests for decisions, validation, escaping, provenance, and path safety.
- [x] Add generated-project and Copier smoke coverage.
- [x] Create the separate Git-managed team-sharing backlog plan.
- [x] Run required validation and archive this plan.

## Validation Notes

- `python3 tests/test-human-report.py` passed 6 focused tests covering generate, skip, blocked, disabled, escaping, deterministic rendering, provenance, unsafe sources, invalid IDs, and symlink boundaries.
- `scripts/lint-project-workflow.sh` passed the static template checks, root policy checks, 77 focused Python tests, and root plan lifecycle test.
- `tests/smoke.sh` passed all generated-project fixtures and pairwise Copier combinations, including execution of the generated human-report CLI and Git-ignore verification; actionlint was unavailable and skipped because no GitHub Actions file changed.
- `tests/copier-minimum.sh` passed the minimum supported Copier and Python compatibility lane.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
- `tests/copier-update.sh` now asserts that supported updates install the managed policy, configuration, and CLI with the safe local default; this test requires a committed target ref and is run after the implementation commit.
