# Let one owner authorization given at plan start cover each same-plan continuation up to the fourth review

status: backlog
primary_invariant: A same-plan continuation proceeds without a new owner message only when the owner recorded a standing authorization for that exact plan and execution genesis before its first formal review; every continuation still writes its own bound authorization record, the cumulative four-review limit is unchanged, and the stop after the fourth review always needs a fresh owner decision.
task_types:
  - planning_docs
  - template_workflow
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"continue, continue-final and continue-fourth-review each read a mode-0600 authorization record whose owner_authorization is a bounded quotation, validated for shape only, and every other field is bound to the exact stopped predecessor, child and registry, so a standing quote can be verified without weakening those bindings.","kind":"existing_mechanism"}
  - {"evidence":"prepare-parent-direct creates the reviewer registry, continuation registry and epoch-0 ledger in one call before any review, which is the point where a standing authorization can be bound to the plan digest and execution genesis.","kind":"existing_mechanism"}
  - {"evidence":"Plan 410 stopped at descope_pending after its first formal review on 2026-09-26 and needed a separate owner message to continue, although the owner wanted continuation through the fourth review approved in advance.","kind":"reproduced_defect"}
completion_conditions:
  - A standing continuation authorization is a mode-0600 record outside the repository with the bounded owner quotation, created once for an exact plan path, plan digest, source head and epoch-0 execution genesis before any formal review, and refused after the first review, for another plan or genesis, or a second time.
  - A derive command writes the unchanged schema-1, schema-2 or schema-3 authorization that continue, continue-final or continue-fourth-review requires for the current stopped ledger, with the standing quotation, plus a private derivation receipt binding the standing record digest to the derived authorization digest; each derived file passes its continuation command.
  - The cumulative four-review limit, the one-child-per-stopped-ledger rule and every eligibility check are unchanged, a standing-enabled run with two reviews in epoch 1 is still refused continue-final, and resolve-owner and owner-accept refuse a standing authorization and require a fresh owner record.
  - An execution without a standing record stops for the owner at each exhausted epoch exactly as before, and every existing continuation test passes unchanged.
  - A verify command accepts a derived authorization only when its derivation receipt, the standing record and the ledger it continues agree, and rejects a receipt for another plan, genesis, epoch or authorization digest.
  - AGENTS.md, orchestration guidance and the orchestrator skill state that a standing authorization given at plan start counts as the owner decision for each continuation up to the fourth review, and the root policy checker asserts it.
  - Both Review-Finding Budgets sections describe the standing rule identically after the path rewrite, both plan-execution-state.py copies stay byte-identical, and the generated AGENTS body and orchestration copy state the same rule.
completion_witness_map:
  - {"condition_sha256":"sha256:c855b18c7ab07e43a6377820378566d648045b8b8b6420f2c0d7121d7fd824e0","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:127daf2749cc1b28c90b2595f63dc7a15bf45c36d2a41c0213816479985c756a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:ffbb9f1fd0ef837961e4ff5bf048085e5de41ee022eefab5e2820115b7927cbe","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:c88bce0979af81d5c75ad0279f3fac0faeda195cd4029bc4aa2c6bdf1c4b0063","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:fcca723135dcc7d4ea0c681de1b584b4ca5c631e9bdd1cd594b1a8f2e52d4e0c","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:25fdf7ce5ef498f6ed5abe2fce6e4e82037d9c7a1229f05caf69d90f8e70e084","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:b447cbf24f687657852df923d3dcb2266eb52ce863b9da6901f1e99273019363","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - AGENTS.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - scripts/check-root-agent-policy.py
  - CHANGELOG.md
preservation_scope:
  - none
context_files:
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - docs/plan/checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md
  - docs/plan/checked/2026/09/16-31/400-register-typesafe-with-canonical-host-detection.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An owner who approves continuation through the fourth review once at plan start is not asked again before the fourth review's stop, unless a stop is ineligible for continuation or is not a review-budget stop.
  - Every continuation still records a bound authorization, the four-review maximum is unchanged, and projects that record no standing authorization behave exactly as before.
  - Root and generated policy, specification and execution-state copies state and implement the same standing rule.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:fa37dda8118e4002ab51592dc786cb42c62181d62050a24dbd95c98c41ca2ca0","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:0a8da5fc6db65a5b2601a357b6379591ef65376239ad3942864bf2e6fb58b3a0","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:4a43ff81fe116a70d502c0e536aeeb26f4c2582e5bb54a0ec5c461f7d7d91266","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: プランの開始時にオーナーが一度だけ与えた承認で、4 回目のレビューまでの同じプランの続行をまかなえるようにする。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger. The owner chose option A on 2026-09-26: one approval at plan start covers continuations through the fourth review, then the owner decides.
- Add a standing-authorization command that writes one mode-0600 record outside the repository, bound to the plan path and digest, source head, epoch-0 genesis, the continuation registry identity and the bounded owner quotation, and refuse it once the ledger has any formal review.
- Add a derive command that writes the existing schema-1, schema-2 or schema-3 continuation authorization for the current stopped ledger from the standing record, and a separate mode-0600 derivation receipt binding the standing record digest, the ledger it continues and the derived authorization digest. The existing continue, continue-final and continue-fourth-review validators and their exact key sets stay unchanged; a verify command checks the receipt.
- Never derive the schema-4 resolve-owner authorization or the owner-accept decision from a standing record; the stop after the fourth review always needs a fresh owner record.
- Keep stops as recorded ledger states. With a standing record the parent continues within the same conversation after each stop and reports every stop, finding severity and continuation in the plan's Validation Notes.
- In standing mode, continue as soon as an eligible review-budget stop is recorded, before spending another review in the same epoch. Diagnosis, repair, replanning, descope and every ineligible stop still wait for the owner.

## Tasks

- [ ] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the unchanged baseline results of the focused suites.
- [ ] Implement the standing-authorization and derive commands and their refusals in both copies.
- [ ] Add cases for creation before and after a review, wrong plan or genesis, a second record, derivation for epochs 1 to 3, schema-4 refusal and the unchanged path without a standing record.
- [ ] State the standing rule in AGENTS.md, the generated AGENTS body, both Review-Finding Budgets sections, both orchestration copies, both orchestrator skills, the root policy checker and CHANGELOG.md.
- [ ] Record a passing adversarial preflight, obtain independent review through a fresh read-only Codex reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26 asked to define these environment and workflow changes as rules and to create plans for them: create each task worktree's .venv with uv, let Bubblewrap run the .venv Python, replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium, fix the check-time plan-id reservations, and approve continuations up to the fourth review once at plan start (option A).
