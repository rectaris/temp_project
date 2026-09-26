# Replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium in writable routing, helper profiles and generated projects

status: backlog
primary_invariant: No shipped or seeded configuration selects the retired gpt-5.3-codex-spark: writable work that is eligible for delegation runs on gpt-5.6-terra medium, the gpt-5.6-luna max availability fallback and the Sol review role are unchanged, and a generated project's own non-retired model choices are never rewritten.
task_types:
  - template_workflow
  - skill_authoring
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"On 2026-09-26 codex-cli 0.157.0 exec with gpt-5.3-codex-spark returned status 400 saying the model is not supported, so every default low/low runner attempt and both Spark helper profiles fail and fall back or stop.","kind":"reproduced_defect"}
  - {"evidence":"The OpenAI Codex changelog entry of 2026-09-14 states that GPT-5.3-Codex-Spark was deprecated and is no longer available in the Codex app, CLI or IDE extension, and asks users to update configurations, custom agents and scripts that select it.","kind":"existing_mechanism"}
  - {"evidence":"select_plan_writable_profile returns Spark for low/low and Terra medium when neither input is high, and Spark is pinned in AGENTS.md, orchestration guidance, two root and two template helper profiles, the runner constants, both policy checkers, SEEDED_AGENT_PROFILES in validate-copier-update.py and update_agent_model_profiles.py.","kind":"existing_mechanism"}
  - {"evidence":"update_agent_model_profiles.py fills only absent model fields and validate-copier-update.py rejects replacing a declared model, so an existing generated project keeps a declared Spark value unless this plan admits that one retired-value transition.","kind":"existing_mechanism"}
completion_conditions:
  - select_plan_writable_profile returns gpt-5.6-terra medium whenever neither implementation_risk nor implementation_ambiguity is high and refuses either high, the one gpt-5.6-luna max availability fallback and the Sol rejection are unchanged, and no runner constant names gpt-5.3-codex-spark.
  - The root and template fast_scoped_worker and sequential_plan_worker profiles use gpt-5.6-terra with medium reasoning and keep their instructions, and every other seeded profile is unchanged.
  - Root and generated AGENTS instructions, orchestration guidance and the sequential orchestrator skill state the Terra-only writable route, the Luna max fallback and the Sol review reservation, name Spark only as retired, and the policy checkers pin those statements.
  - update_agent_model_profiles.py and both transition validators replace only a declared model value gpt-5.3-codex-spark with gpt-5.6-terra, keep a declared reasoning value, supply medium only when absent, and refuse every other model, reasoning or non-model change except the one exact legacy-worker-to-read-only-Terra transition.
  - A real Copier update migrates read-only Spark profiles and the supported legacy workspace-write sequential worker to read-only Terra, keeps a declared non-medium reasoning value, and leaves every other project-owned byte unchanged.
  - ownership.yaml, SPEC_COPIER_ADOPTION.md and references/template-development.md state the retired-model exception, and the template checker and both CURRENT_OWNERSHIP_SHA256 values match the updated ownership record.
completion_witness_map:
  - {"condition_sha256":"sha256:ba643922c6123af3168e5e8b307ef765bec8314c0ad1d689eb9301ee5fe7314b","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:2b73c1623095dc45aad03a894ff86a8e0595a891b33ecd03a9685c203aacc917","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:c9d46f2874edc4bd618d9b46708f8754bd4958dae385fc85fa28825a50e0e334","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:790e86078e97d2b526e98e2283fd3c195ac5affb82bebf861c2a807d74de0a3c","witness":"python3 tests/test-copier-migration.py"}
  - {"condition_sha256":"sha256:7558074f5cd3ad4574adeaad6f430d5ce48ac64fd62d03c0f82e680ea1ae21c9","witness":"tests/copier-update.sh --require-copier"}
  - {"condition_sha256":"sha256:5ba59c49359ea354c736a23677a636f0a47c9204cdf9bfb38766e505f1c8414e","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - AGENTS.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - .codex/agents/fast_scoped_worker.toml
  - .codex/agents/sequential_plan_worker.toml
  - template/.codex/agents/fast_scoped_worker.toml
  - template/.codex/agents/sequential_plan_worker.toml
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - tests/assert-generated-semantics.py
  - tests/smoke.sh
  - CHANGELOG.md
  - scripts/update_agent_model_profiles.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - tests/test-copier-migration.py
  - tests/copier-update.sh
  - scripts/plan_validation_commands.py
  - scripts/migrate-sequential-plan-worker.py
  - template/.project-agent-workflow/scripts/migrate-sequential-plan-worker.py
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - references/template-development.md
  - copier.yml
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
  - python3 tests/test-copier-migration.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The availability-only gpt-5.6-luna max fallback, the refusal of high-risk or high-ambiguity writable delegation and the Sol review reservation are unchanged.
  - No shipped or seeded configuration, instruction or script selects the retired gpt-5.3-codex-spark, and eligible writable work runs on gpt-5.6-terra medium.
  - Existing generated projects are migrated off the retired model on update without rewriting any other project-owned choice.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:60ebf090ff92f121ebdb9f57b62398949aee0964460523f6861d589b14968bb3","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:61e8891ed791d7c96d568c69dd4ad74729c43a6af0e46c184002f59c38189d0a","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:9ef4ce68d2aff4c5161f68976493df61113d8d10807e0eef6a6238160484de79","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
integration_gates:
  - https://learn.chatgpt.com/docs/changelog#codex-2026-09-14-codex-spark-deprecation records the retirement this plan responds to.
checked_summary_ja: 提供が終了した gpt-5.3-codex-spark を、書き込みの経路、補助のプロファイル、生成先のプロジェクトで gpt-5.6-terra の medium に置き換える。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger, because this plan changes validation-authority checkers and the Copier update transition rules.
- Collapse the writable route to one model: gpt-5.6-terra with medium reasoning whenever neither classification is high. Keep DEFAULT_CODEX_MODEL as the Terra value, remove the separate Spark route, and keep explicit nonblank overrides and the Sol rejection.
- Keep gpt-5.6-luna max as the single availability fallback on the same Codex CLI error classes. Do not use Luna for ordinary edits.
- Move fast_scoped_worker and sequential_plan_worker to gpt-5.6-terra medium in both layouts; their roles and instructions are unchanged.
- Treat gpt-5.3-codex-spark as a retired value, not a project choice: the updater and both transition validators may replace exactly that declared model with gpt-5.6-terra, keep any declared reasoning value, and supply medium only when reasoning is absent. Record the exception in ownership.yaml, SPEC_COPIER_ADOPTION.md and references/template-development.md.
- Keep historical bytes unchanged: checked archives, sealed orchestration fixtures and the migrator's LEGACY_PROFILE input. Change the migrator's READ_ONLY_PROFILE output to Terra, and have the updater leave the exact legacy input for the migrator, so the supported legacy worker still ends read-only on Terra; change copier.yml only if the hook order must change.
- Add python3 tests/test-copier-migration.py to the root validation-command allowlist in scripts/plan_validation_commands.py, because this plan declares it as a focused witness.
- Keep one exact historical transition: the validators admit the legacy workspace-write sequential worker becoming the read-only Terra profile by its exact input and output digests, with the output digest updated in both validators; every other non-model byte stays refused.

## Tasks

- [ ] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the unchanged baseline results of the focused suites.
- [ ] Add python3 tests/test-copier-migration.py to the root validation-command allowlist.
- [ ] Change the runner routing and constants in both copies, and update the routing and fallback cases.
- [ ] Move the two helper profiles to Terra in both layouts and update AGENTS instructions, orchestration guidance, the orchestrator skill, both policy checkers, the generated-semantics assertions, smoke and CHANGELOG.md.
- [ ] Add the retired-value migration to the updater and both transition validators, with cases for Spark migration and for refusing every other replacement, and extend the Copier update test with a Spark-declaring project.
- [ ] Record a passing adversarial preflight, obtain independent review through a fresh read-only Codex reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26 asked to define these environment and workflow changes as rules and to create plans for them: create each task worktree's .venv with uv, let Bubblewrap run the .venv Python, replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium, fix the check-time plan-id reservations, and approve continuations up to the fourth review once at plan start (option A).
