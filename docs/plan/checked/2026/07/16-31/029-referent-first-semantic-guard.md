# Add referent-first semantic guardrails

status: ready_to_archive
task_type: template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
target_files:
  - AGENTS.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/spec-index.yaml
  - .codex/hooks.json
  - .codex/hooks/semantic_guard_advisory.py
  - .codex/skills/define-referents-first/SKILL.md
  - .codex/skills/define-referents-first/agents/openai.yaml
  - .codex/skills/define-referents-first/references/workflow.md
  - scripts/referent-contract.py
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - template/AGENTS.md.jinja
  - template/docs/agent/SPEC_REFERENT_FIRST.md
  - template/docs/agent/spec-index.yaml.jinja
  - template/.codex/hooks.json.jinja
  - template/.codex/hooks/semantic_guard_advisory.py
  - template/.codex/skills/define-referents-first/SKILL.md
  - template/.codex/skills/define-referents-first/agents/openai.yaml
  - template/.codex/skills/define-referents-first/references/workflow.md
  - template/scripts/referent-contract.py
  - tests/fixtures/referent-contract/
  - tests/test-referent-contract.py
  - tests/test-hooks.py
  - tests/smoke.sh
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - git diff --check
acceptance:
  - Root and generated projects receive semantically aligned referent-first policy, skill, CLI, advisory hook, and validation behavior.
  - The CLI preserves unknowns, seals referents before labels, records lifecycle transitions, validates controlled terms, and renders a semantic diff.
  - Advisory hooks restore or report incomplete referent contracts without parsing unstable transcript formats or blocking unrelated work.
  - Fixed median, edge, negative, and hold-out fixtures cover critical semantic requirements without embedding expected answers in the skill.
  - Template static checks and smoke tests verify every generated artifact and the root/template synchronization boundary.
  - Required repository validation passes before archival and commit.
expected_output: full-implementation
checked_summary_ja: 語を付ける前に指示対象と不明点を固定する意味検査をrootと生成テンプレートへ追加した。

## Problem

Codex can introduce a fluent label before its concrete referent, semantic kind, evidence, or causal order is settled, allowing one term to collapse conditions, values, events, states, or multi-step reasoning.

## Goal

Add a reusable, testable referent-first workflow that prevents premature naming, preserves unresolved facts, validates file-based artifacts, and supports independent semantic review without making every task blocking.

## Decisions

- Use `docs/agent/SPEC_REFERENT_FIRST.md` as normative project policy and `define-referents-first` as the concise operational skill.
- Install the policy and skill in both the root self-application and generated template using the repository's established `.codex/skills` boundary.
- Use a task-kind-aware JSON contract with shared referent fields instead of one universal Markdown table.
- Treat `unknown` and `disputed` as first-class certainty states and prohibit labels for those referents.
- Enforce visible artifact order through a deterministic lifecycle CLI and a sealed referent projection hash; do not claim that a hash proves hidden model reasoning order.
- Keep runtime hooks advisory and filesystem-based; do not parse Codex transcripts as a required interface.
- Gate only contracts or target documents that explicitly opt into the workflow; do not classify every Markdown file as blocking.
- Keep independent semantic evaluation separate from the authoring skill and store fixed scenarios under test fixtures.
- Preserve the current repository skill-discovery layout; treat any migration to another discovery path as separate compatibility work.
- Keep local contract instances under ignored `.agent-artifacts/referent-contracts/` by default.

## Implementation Instructions

1. Add concise root and generated policy routing and keep Japanese policy copies semantically aligned.
2. Create the `define-referents-first` skill with UI metadata and one directly linked workflow reference.
3. Implement a dependency-free JSON contract CLI with explicit lifecycle transitions, schema checks, semantic-diff output, and self-testable behavior.
4. Add an advisory hook that reports incomplete contracts at session restoration and turn completion without blocking ordinary tasks.
5. Add fixed evaluation scenarios and requirements outside the skill, plus deterministic unit and generated-project smoke coverage.
6. Register all root and template artifacts in static policy checks and Copier required-file lists.
7. Run required validation, record concise evidence, mark the plan ready, archive it with the lifecycle script, and commit the scoped work.

## Tasks

- [x] Add policy, routing, skill, and metadata to root and template.
- [x] Add the referent contract lifecycle CLI and semantic diff.
- [x] Add advisory hook behavior and deterministic tests.
- [x] Add fixed evaluation fixtures and generated smoke coverage.
- [x] Run validation, archive this plan, and commit the completed change.

## Validation Notes

- `python3 scripts/validate-changes.py --all` passed.
- `scripts/lint-project-workflow.sh` passed, including 15 hook tests and 8 referent-contract lifecycle tests.
- `tests/smoke.sh` passed for all Copier fixtures and the generated referent-contract lifecycle.
- Skill Creator `quick_validate.py` passed for root and template `define-referents-first` skills.
- `git diff --check` and root/template byte-alignment checks passed.
- Independent empirical evaluation remains pending because this run was not authorized to start fresh evaluator agents; fixed median, edge, negative, and hold-out inputs are committed for that later evaluation.
