# Pin Spark workers in root and generated projects

status: checked
task_types:
  - template_workflow
review_class: B
human_design_required: yes
human_approval_status: approved
write_scope:
  - .codex/agents/
  - docs/plan/
  - references/orchestration.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.codex/agents/
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - template/docs/plan/sub-agents/
  - tests/
context_files:
  - none
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Pin read-only exploration to Luna low, documentation research to Luna medium, ordinary scoped implementation to Terra medium, and change review to Sol high in root and generated projects.
  - Pin sequential_plan_worker to gpt-5.3-codex-spark with medium reasoning in both root and Copier-generated projects.
  - Add fast_scoped_worker to root and generated projects for bounded, reversible code changes with predetermined validation.
  - Keep deterministic command execution, final integration, commits, releases, and high-risk decisions in the main session.
  - Require generated-artifact and root-policy checks to enforce the fixed Spark configuration and worker contract.
checked_summary_ja: root と Copier 生成先に Spark 固定の計画実装用および小規模実装用エージェントを追加し、役割境界を検証する。

## Decisions

- Pin Spark without a Copier question or availability fallback in generated agent definitions.
- Pin every generated helper role to its task-specific model and default reasoning effort instead of inheriting an environment default.
- Use medium reasoning as the file-level default for both Spark workers.
- Keep scoped_worker as the general bounded implementation role and add fast_scoped_worker as a separate low-ambiguity coding role.
- Do not delegate short deterministic commands solely to obtain pass or fail results.

## Tasks

- [x] Add and align the root and generated Spark worker definitions.
- [x] Document routing, escalation, and main-session ownership boundaries.
- [x] Replace the former portability assertions with fixed task-specific model configuration checks.
- [x] Run completion validation and archive this plan.

## Validation Notes

- Fixed model profiles: repo_explorer uses Luna/low, docs_researcher uses Luna/medium, fast_scoped_worker and sequential_plan_worker use Spark/medium, scoped_worker uses Terra/medium, and change_reviewer uses Sol/high.
- fast_scoped_worker stops on scope expansion, architecture or policy decisions, security or authorization questions, destructive or external writes, unexpected tracked-file deletion, conflicts, and unclear validation failures.
- `scripts/lint-project-workflow.sh` passed all static, unit, migration, Hook, validation-tool, and root lifecycle checks.
- `tests/smoke.sh` passed Copier rendering and managed workflow checks across generated profiles. GitHub Actions lint was skipped because actionlint is not installed.
- `COPIER_UPDATE_TARGET_REF=3f727c3febfa3c425607bc5d63a37fe9ade14a62 REQUIRE_COPIER=1 tests/copier-update.sh` passed against a temporary commit object containing the candidate changes.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
