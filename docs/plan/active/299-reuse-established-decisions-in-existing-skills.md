# Reuse established decisions through existing planning skills

status: in_progress
primary_invariant: Existing planning and execution skills apply one shared decision sequence to the same authorized task without reopening settled choices, inventing successor plans or relaxing normative approval, diagnosis and review boundaries.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"decision-audit already skips mechanical and settled choices; implementation-guidelines prefers reproduce-first fixes; the sequential skill already owns parent acceptance and stopped-run boundaries.","kind":"existing_mechanism"}
  - {"evidence":"Plan 282 checks one authoring input for requirement, path, condition and witness coverage. The Plan 119 record documents root/generated diagnosis confusion.","kind":"existing_mechanism"}
  - {"evidence":"Plan 275 relocates detailed policy only. Operational decision reuse is a separate bounded change following that relocation.","kind":"existing_mechanism"}
completion_conditions:
  - One direct reference contains accepted-decision reuse, requirement/scope/condition/witness preflight and exact-failure reproduction sections, with resolvable conditional links from existing skills.
  - The policy checker loads the fixed scenario fixture and validates required case ids, authorization expectations and policy-reference coverage for unchanged work, changed requirements, safety, external effects, formal diagnosis and stopped budgets.
  - Concise aligned skill bodies treat project policy as normative and add no new skill, state record, evaluation service, numbered investigation or parallel planning authority.
completion_witness_map:
  - {"condition_sha256":"sha256:b6498ea62e278f9f1444cd4c0bbad753154968d8fcc1aeef64f761dfdc502c0a","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:7ac045986249ae2da02438dd0a79b155225a53fa338c0e4b4e4ef3aaed121658","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:ae22add1bf5cd30d0e69cb2eea96f5eed2c7a22c5f4d4944ec70147fc2e3312d","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .codex/skills/decision-audit/SKILL.md
  - .codex/skills/decision-audit/references/implementation-preflight.md
  - template/.project-agent-workflow/skills/decision-audit/SKILL.md
  - template/.project-agent-workflow/skills/decision-audit/references/implementation-preflight.md
  - .codex/skills/implementation-guidelines/SKILL.md
  - template/.project-agent-workflow/skills/implementation-guidelines/SKILL.md
  - .codex/skills/sequential-plan-orchestrator/SKILL.md
  - template/.project-agent-workflow/skills/sequential-plan-orchestrator/SKILL.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md
  - scripts/check-root-agent-policy.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/fixtures/agent-policy-routing/scenarios.json
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/plan/replanned/2026/09/01-15/275-route-detailed-agent-policy-on-demand.md
  - docs/plan/checked/2026/09/01-15/302-complete-routed-agent-policy.md
  - docs/plan/checked/2026/09/01-15/282-render-plans-from-checked-authoring-input.md
  - docs/plan/checked/2026/08/16-31/119-integrate-verify-copier-update-skill.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - One direct reference contains accepted-decision reuse, requirement/scope/condition/witness preflight and exact-failure reproduction sections, with resolvable conditional links from existing skills.
  - The policy checker loads the fixed scenario fixture and validates required case ids, authorization expectations and policy-reference coverage for unchanged work, changed requirements, safety, external effects, formal diagnosis and stopped budgets.
  - Concise aligned skill bodies treat project policy as normative and add no new skill, state record, evaluation service, numbered investigation or parallel planning authority.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:b6498ea62e278f9f1444cd4c0bbad753154968d8fcc1aeef64f761dfdc502c0a","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:7ac045986249ae2da02438dd0a79b155225a53fa338c0e4b4e4ef3aaed121658","stage":"focused","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"acceptance_sha256":"sha256:ae22add1bf5cd30d0e69cb2eea96f5eed2c7a22c5f4d4944ec70147fc2e3312d","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after this backlog plan is selected for implementation and published as active; use its exact bound task worktree.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - Start after existing Plan 275 is checked. Do not expand 275 itself into skill redesign.
  - Apply system skill-creator guidance during implementation; preserve concise bodies and direct references.
  - Do not change external-service policies, ledger schemas, approval fields, correction budgets, human-report checks or authoring input formats.
checked_summary_ja: 既決事項と失敗の再現確認を既存スキルへまとめ、計画作成と承認要求の重複を減らす。

## Decisions

- After Plan 275, add one direct reference to decision-audit and short conditional links from implementation and sequential skills. Preserve normative policy in existing specifications.
- Identify the requested outcome and accepted decision evidence; distinguish product repair from a request to improve development procedures. Reuse settled choices while requirements, safety and effects remain unchanged.
- Before long plan prose, use the existing authoring check to inspect requirement/path/condition/witness coverage, including counterparts and test-registration files. Require no new form or numbered feasibility plan.
- After formal failure, preserve diagnosis_required and reproduce the exact operation, input, directory and status before proposing repair. This reference grants no independent diagnosis or repair authority.
- A new id, routine checkpoint or skill invocation does not alone require repeated approval. Changed requirements, expanded effects and stopped-run continuation retain existing explicit authorization.
- Use fixed examples and one independent reader evaluation. Routing tests do not prove language understanding or productivity; retain fixed cases when assessing findings.
- Keep the independent reader result as separate semantic evidence for decision reuse and no universal approval gate; the fixture checker proves only its named structural predicates.

## Tasks

- [ ] Record cases for unchanged authorized work, expanded effects, root/generated failure confusion, plan-only requests, absent feasibility and review exhaustion.
- [ ] Create the direct reference and replace duplicated operational explanations with conditional links in existing skills; keep names and trigger scope stable.
- [ ] Align policy and installation inventory without copying the entire lifecycle contract into the skill.
- [ ] Extend check-root-agent-policy.py to load tests/fixtures/agent-policy-routing/scenarios.json and reject missing cases, invalid expectation values and unresolved policy links. These checks establish fixture and routing structure, not agent behavior.
- [ ] Obtain one independent reader review against fixed cases and report observed misinterpretations and unobserved timing separately.
- [ ] Run focused checks and the mandatory suite once for the accepted change.

## Validation Notes

- Planning baseline: b3e300888412f7e9c2fb243435da4cb4082f5135 in temp_project.
- Owner instruction: 提案の方針でプランを作成せよ。変更点が多い場合は複数のプランとして作成せよ。手続きとして削減するべき部分をまとめたり、スキル化、関数化するべき部分など、改善できる部分をまとめよ。
- This instruction authorizes plan authoring, not implementation or reopening a stopped run. This is ordinary backlog work, not a reconstruction successor.
- See docs/plan/backlog/README.md for procedure reductions, existing-plan reuse and implementation order. Full decision audit stays in local development-process-planning evidence.
- The shared authoring checker derives correspondence and digests; the parent reviews witness semantics. No measured productivity saving is claimed.

- 2026-09-09 activation: Owner instruction 「@docs/plan/backlog/ にあるそれぞれのプランついて、実装作業をせよ。」 selected this backlog plan for implementation. `review_class: B` with `human_approval_status: not_required`, so no separate design approval is needed.
- 2026-09-09 predecessor gate: The gate "Start after existing Plan 275 is checked" is satisfied by its successor. Plan 275 stopped at `replan_required` and was reconstructed as plan 302, which carries every acceptance item of 275 unchanged and is now checked at `docs/plan/checked/2026/09/01-15/302-complete-routed-agent-policy.md`. The relocation this plan waits for is therefore in place; `context_files` is rebound to the archived 275 record and its checked successor.
- 2026-09-09 activation baseline: `dfba0d9` in `temp_project`.

- 2026-09-09 candidate: `c817f20`..`299ff52` on `plan/299-reuse-established-decisions-in-existing-skills` adds the shared implementation-preflight reference, routes it from the three existing skills, states the preflight in `SPEC_DECISION_AUDIT.md`, and pins the route by checker-owned expectations in `scripts/check-root-agent-policy.py` and `scripts/check-copier-template.py`. All 14 changed paths are inside `write_scope`.
- 2026-09-09 focused validation: `python3 scripts/check-root-agent-policy.py`, `python3 scripts/check-copier-template.py`, `python3 tests/test-validation-tools.py` (245), `python3 scripts/validate-changes.py --all`, and `git diff --check` each passed on the candidate. Preflight only, not authoritative: `tests/copier-update.sh --require-copier` passed and the two new template paths appear in the expected generated set.
- 2026-09-09 review: Four independent reviews across two epochs, the cumulative maximum. Epoch 0 round 1 found two Medium findings, remediated in `2dcdd46`. Epoch 0 round 2 found two Medium findings, remediated in `2015a56` after the owner authorized one continuation epoch. Epoch 1 round 1 found one Medium finding, remediated in `299ff52`. Epoch 1 round 2, the final permitted review, still returned one Medium finding.
- 2026-09-09 open finding: `markdown_operative_lines()` in `scripts/check-root-agent-policy.py` ends a fenced code block on any line whose stripped form starts with the opening fence token. CommonMark closes a fence only when the closer is indented at most three spaces, repeats the opening character at least as many times, and carries no info string. A closer such as ```` ```not-a-closing-fence ```` or a four-space-indented closer therefore ends the block for the checker but not for Markdown, so a routed instruction can stay inside a code block while both checkers pass. The reviewer reproduced this across all six root and generated skill files.
- 2026-09-09 stop: The execution epoch's independent review budget is exhausted and the one owner-authorized continuation epoch is already spent, so no further remediation round is available inside this plan. Recorded `status: replan_required` with `parent_remediation_budget_exhausted`. The candidate is retained unpublished on its branch and no acceptance item is withdrawn. Awaiting an owner decision on continuation authorization or reconstruction.
- 2026-09-09 owner continuation authorization: Asked the owner to choose between continuation, reconstruction, deferral, and stopping. The owner answered `authorize_continuation`, quoted as 「継続を承認する（新エポックで残り 1 件を修正し、最終レビューまで進める）」, under the standing instruction 「@docs/plan/backlog/ にあるそれぞれのプランついて、実装作業をせよ。」. This authorizes one further execution epoch on the unchanged plan, source baseline, invariant, and acceptance items. No requirement, safety condition, validation authority, or write scope changes.
- 2026-09-09 reopen: `status` returns to `in_progress` for the authorized epoch. The open finding is narrow and inside `write_scope`, so the epoch remains bounded to the fenced-code closer condition and its evidence.
- 2026-09-09 epoch 2 review: Round 1 found two Medium findings, a tab-indented fence inside a list item and a raw HTML block, both remediated in `de6773a`. Round 2, the last of the epoch, found one Medium finding: fence and HTML detection still read physical lines, so a fence indented past the margin inside numbered item 7, or raw HTML opened as list content, still hid a byte-identical route.
- 2026-09-09 design change: Six review rounds each found one further construct, which is evidence that enumerating hiding places is the wrong shape for this check. `bd872b9` replaces the approximation. A file that carries a routed instruction may now contain no code fence token, no tab, no HTML comment marker, and no block that opens with a raw HTML tag after blockquote and list markers are removed. Without those tokens no container can turn a line into anything but text, so the argument no longer depends on reconstructing container context. The cost is that these three skills and the shared reference can no longer hold fenced examples; the refusal names the offending line.
- 2026-09-09 evaluation against a reference parser: `markdown_it` in CommonMark mode was used as an oracle, not as a shipped dependency. Across 240 systematic and 4000 randomized constructs that wrap the exact route in fences, comments, raw HTML, and list or blockquote containers at varying indentation, no construct hid the route from the parser while the rule accepted it. The eight route-carrying and reference files, unmodified, report no defect. Fifteen end-to-end mutations of both checkers, including the two open findings, were all rejected, as were the seven that also apply to `scripts/check-copier-template.py`.
- 2026-09-09 focused validation on `bd872b9`: `python3 scripts/check-root-agent-policy.py`, `python3 scripts/check-copier-template.py`, `python3 tests/test-validation-tools.py` (245), `python3 scripts/validate-changes.py --all`, and `git diff --check` each passed.
- 2026-09-09 stop: The authorized epoch's review budget is spent, so the candidate cannot be reviewed again inside this plan. Recorded `status: replan_required` with `parent_remediation_budget_exhausted`. The remediation is committed and unpublished; no acceptance item is withdrawn.
- 2026-09-09 owner continuation authorization, second: Presented the stop, the changed shape of the check, its cost, and the reference-parser evidence, and asked the owner to choose between continuation, acceptance without further review, reconstruction, deferral, and stopping. The owner answered `authorize_continuation`, quoted as 「継続を承認する（もう 1 エポック開き、最終レビューと正式検証まで進める）」. This authorizes one further execution epoch on the unchanged plan, source baseline, invariant, acceptance items, validation authority, and write scope. The owner did not waive review.
- 2026-09-09 reopen, second: `status` returns to `in_progress` for the third authorized epoch, bounded to the container-context finding and its evidence.
- 2026-09-09 epoch 3 review: Round 1 found one Medium finding, a multiline inline code span opened by one or two backticks. Remediating it exposed a fault in the reference-parser harness itself, which had been removing inline code regions and therefore reporting legitimate code in the route as hidden. Rebuilding the harness on the parser's own token stream immediately surfaced a real hole the earlier harness had masked, an indented link reference definition inside a list container. Round 2, the last of the epoch, found three Medium findings: an image or reference label left open, a backslash-escaped backtick pair concealing an HTML comment, and an escaped closing parenthesis defeating the link-destination rule.
- 2026-09-09 remediation, unreviewed: `33a08e4` and `f3138dc` remove backslash escapes before any delimiter is read and require every line to close the labels it opens. All three round 2 findings are addressed, but no independent review has seen this state.
- 2026-09-09 harness correction: The harness previously compared a heading against its own source markers, which a renderer never emits, so it reported every marked line as hidden and produced 215 unexplained results. With headings and list markers normalized, 125,000 randomized adversarial constructs across six seeds hid a route 15,599 times and were accepted zero times, and the eight route-carrying files report no defect unmodified. 152 end-to-end mutations, covering all eight files and all eighteen carriers including the three round 2 findings, were each rejected from a clean clone.
- 2026-09-09 focused validation on `f3138dc`: `python3 scripts/check-root-agent-policy.py`, `python3 scripts/check-copier-template.py`, `python3 scripts/validate-changes.py --all`, and `git diff --check` each passed.
- 2026-09-09 stop: The third authorized epoch's review budget is spent. Accepted closure requires the latest review to have cleared High and Medium findings, and the latest review returned three, so this candidate cannot be accepted without a further review even though the findings are addressed. Recorded `status: replan_required` with `parent_remediation_budget_exhausted`. The remediation is committed and unpublished; no acceptance item is withdrawn.
- 2026-09-09 owner continuation authorization, third: Presented the stop, the addressed findings, the harness fault that had inflated earlier evidence, and the rule that blocks accepted closure without a clearing review, and asked the owner to choose between continuation, reconstruction, deferral, and stopping. The owner answered `authorize_continuation`, quoted as 「継続を承認する（4エポック目・確認レビュー1回で完了まで）」. This authorizes one further execution epoch on the unchanged plan, source baseline, invariant, acceptance items, validation authority, and write scope. No requirement or safety condition changes.
- 2026-09-09 reopen, third: `status` returns to `in_progress`. The epoch is bounded to one confirming review of the committed remediation and, if it clears, the single authoritative validation run and completion. No new implementation work is authorized.
