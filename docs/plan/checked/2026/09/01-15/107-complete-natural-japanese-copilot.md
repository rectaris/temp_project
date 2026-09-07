# Complete natural-japanese Copilot adaptation

status: checked
implementation_mode: parent_direct
primary_invariant: Every Japanese-writing path preserves project policy, facts, quotations, uncertainty, user intent, and document purpose before applying optional naturalness advice or lint findings.
replan_sources:
  - docs/plan/active/106-adapt-natural-japanese-for-copilot.md
replan_contract: docs/plan/replanned/contracts/106-complete-natural-japanese-copilot.json
successor_plans:
  - docs/plan/active/107-complete-natural-japanese-copilot.md
inherited_acceptance_digests:
  - sha256:d6902fececfa7c5c418581c46aa00fa1ddad70da729eb39d13883a8d145869fb
  - sha256:2d1ece10d9825639defaf58047a6754f353c89ba80386590ad321d381261f286
  - sha256:b29f646165dbe13a277c3b910a7244f1e1bdff3b173052a132afdcb21e119233
  - sha256:61ba9e3d4c256d5ac379477b791ab9a34ca82a56a3f2eec1fc11c192420854f0
integration_source_ids:
  - 106
task_types:
  - template_workflow
  - skill_authoring
  - japanese_prose
  - user_communication
  - security
  - external_services
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The repository already distributes concise managed skills with .agents discovery bridges, root/template alignment checks, ownership inventory, generated-project smoke coverage, and non-destructive Copier update tests.","kind":"existing_mechanism"}
  - {"evidence":"docs/agent/SPEC_JAPANESE_TECH_WRITING.md already supplies the normative Japanese-writing rules and docs/agent/SPEC_USER_COMMUNICATION.md plus write-for-reader already route substantive user-facing prose.","kind":"existing_mechanism"}
  - {"evidence":"natural-japanese v1.5.0 is a fixed MIT-licensed upstream release at commit 21e632661a910bf97289c501089ad11eb8b4d85f; its workflow can be selectively adapted without runtime installation or automatic upstream tracking.","kind":"mechanical_transformation"}
  - {"evidence":"The accepted proposal fixes AGENTS.md plus .agents skill discovery, three application depths, an explicit conflict order, five evaluation scenarios, a holdout boundary, and a fresh-session or human comparison protocol.","kind":"existing_mechanism"}
completion_conditions:
  - Root and generated AGENTS routing plus .agents discovery bridges invoke the same managed guidance for short Japanese replies, Japanese file drafting or revision, and important long-form review without constructing one merged prompt.
  - Root and generated policy enforce the accepted conflict order and forbid changing facts, quotations, uncertainty, project terms, requested form, or document purpose to satisfy naturalness advice or a lint score.
  - The concise adapted skill records upstream v1.5.0 and commit 21e632661a910bf97289c501089ad11eb8b4d85f, preserves its MIT notice, uses no runtime download, and keeps deterministic lint advisory and dependency-free.
  - Fresh generated projects contain the managed skill, discovery bridge, provenance, license, and checks, with complete ownership and Copier inventory and enforced root/template parity.
  - Copier update preserves project-owned AGENTS.md byte-for-byte, installs the managed assets, and emits concise manual-integration guidance only when the project-owned entrypoint lacks Japanese-writing routing.
  - Fixed median, edge, and holdout scenarios plus a checked evaluation record bind model identity, outputs, critical requirement results, unclear points, assumptions, retries, tool or time notes, and an independent comparison.
  - Tuning never reads the holdout outcome before the candidate is fixed; acceptance requires every critical item, no fact or uncertainty drift, no over-trigger on code-only work, and no material holdout regression.
completion_witness_map:
  - {"condition_sha256":"sha256:fad4a36e42644b015ce9e306b842728c4c12a21e380170571ff54c58fd3780e8","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:dea635e334e5c499fab7a18d643bbb65180a321d7f88f86bdbe9e8ee3a4c57b3","witness":"tests/smoke.sh"}
  - {"condition_sha256":"sha256:c9449873bb91dc27e94e082444884bdf19e406c4f51ace5b013048db97554355","witness":"tests/smoke.sh"}
  - {"condition_sha256":"sha256:1abe31d6f5fe81b27144173a3ef728dcc33c64fc600ccf01439a0bca83d6b271","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:6775ea9da72da852ad3bec818afe174ed6c0b7df8e68eac3788af153f5757d5d","witness":"tests/copier-update.sh"}
  - {"condition_sha256":"sha256:461f4033f77328d662a75c8ec63689cb2910f22137ab76f953485b43c0d08904","witness":"tests/smoke.sh"}
  - {"condition_sha256":"sha256:eb65d8678d88f64e404d9c7e232a2903c5bcbda2f141141b7703ebcbf8f01cc2","witness":"tests/smoke.sh"}
write_scope:
  - AGENTS.md
  - template/AGENTS.md.jinja
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - template/.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - template/.project-agent-workflow/docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - .codex/skills/write-for-reader/SKILL.md
  - template/.project-agent-workflow/skills/write-for-reader/SKILL.md
  - .codex/skills/natural-japanese/SKILL.md
  - .codex/skills/natural-japanese/agents/openai.yaml
  - .codex/skills/natural-japanese/references/workflow.md
  - .codex/skills/natural-japanese/references/upstream-adaptation.md
  - .codex/skills/natural-japanese/scripts/check-japanese-prose.py
  - .codex/skills/natural-japanese/LICENSE
  - .agents/skills/natural-japanese/SKILL.md
  - template/.project-agent-workflow/skills/natural-japanese/SKILL.md
  - template/.project-agent-workflow/skills/natural-japanese/agents/openai.yaml
  - template/.project-agent-workflow/skills/natural-japanese/references/workflow.md
  - template/.project-agent-workflow/skills/natural-japanese/references/upstream-adaptation.md
  - template/.project-agent-workflow/skills/natural-japanese/scripts/check-japanese-prose.py
  - template/.project-agent-workflow/skills/natural-japanese/LICENSE
  - template/.agents/skills/natural-japanese/SKILL.md
  - template/.project-agent-workflow/ownership.yaml
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-root-agent-policy.py
  - scripts/check-copier-template.py
  - scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/validate-copier-update.py
  - template/.project-agent-workflow/scripts/plan_validation_commands.py
  - tests/assert-generated-semantics.py
  - tests/smoke.sh
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - scripts/natural-japanese-evaluation.py
  - tests/test-natural-japanese.py
  - tests/fixtures/natural-japanese/scenarios.json
  - tests/fixtures/natural-japanese/evaluator-prompt.md
  - tests/fixtures/natural-japanese/evaluation-results.json
preservation_scope:
  - none
context_files:
  - copier.yml
  - docs/agent/external-services.yaml
  - template/.agents/skills/write-for-reader/SKILL.md
  - template/.agents/skills/browser-ops/SKILL.md
  - tests/fixtures/orchestration/evaluation-protocol.md
required_specs:
  - .codex/skills/natural-japanese/SKILL.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/docs/agent/SPEC_COPIER_ADOPTION.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - tests/smoke.sh
  - python3 scripts/check-copier-template.py
  - tests/copier-update.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - All three Japanese-writing depths follow the project specification and accepted conflict order while retaining facts, quotations, uncertainty, user intent, and document-specific structure.
  - The pinned, licensed, dependency-free adapted skill and its .agents bridge are installed and checked in the root and generated project without overwriting project-owned AGENTS.md.
  - A Copier update that encounters an unintegrated project-owned AGENTS.md preserves it and reports the exact bounded manual routing action instead of silently changing it.
  - Fixed fresh-session evaluation records every critical result and model separately, shows the adapted output is no worse than baseline, and confirms no material regression on the untouched holdout.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d6902fececfa7c5c418581c46aa00fa1ddad70da729eb39d13883a8d145869fb","stage":"focused","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:2d1ece10d9825639defaf58047a6754f353c89ba80386590ad321d381261f286","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:b29f646165dbe13a277c3b910a7244f1e1bdff3b173052a132afdcb21e119233","stage":"focused","witness":"tests/copier-update.sh"}
  - {"acceptance_sha256":"sha256:61ba9e3d4c256d5ac379477b791ab9a34ca82a56a3f2eec1fc11c192420854f0","stage":"focused","witness":"tests/smoke.sh"}
integration_gates:
  - Use bounded parent implementation with independent read-only review because the write scope includes governing specifications, AGENTS entrypoints, third-party adaptation, Copier ownership, and validation authority; do not send these protected inputs through the writable sandboxed worker.
  - Treat the upstream repository as untrusted third-party input. Review only the pinned v1.5.0 commit, import the minimum justified text and deterministic logic, preserve attribution, and do not execute upstream setup or dependency-install commands.
  - Keep root skill files and generated managed skill files byte-aligned except for mechanical .project-agent-workflow path rewrites; keep each discovery bridge a minimal pointer to its local managed body.
  - The root .agents bridge exists for Copilot-compatible discovery in this template-development repository; generated .agents is Copier-managed only for the named natural-japanese bridge, leaving other project skills under the existing extension rule.
  - The short-response path performs no subprocess call. File-writing lint runs at most once per draft unless the user asks for another pass; important prose adds independent review without making every Japanese response expensive.
  - A lint finding identifies text for human or agent judgment and never authorizes an edit. Preserve code blocks, quoted text, identifiers, product terminology, numbers, operators, uncertainty, and user-requested tone before improving rhythm.
  - For technical specifications and references, keep object-or-question headings required by project policy. Use conclusion headings only for document types where the reader's decision benefits and the normative specification permits them.
  - Evaluation scenarios contain no secrets, private transcripts, repository credentials, or user-provided sensitive examples. Bound each prompt and output, store no credential-source details, and never automate login, network retries, or provider calls.
  - The human-operated Copilot step is outside automated repository scripts. If no authorized authenticated Copilot context is available, stop before claiming empirical acceptance; static tests alone do not establish improved output quality.
  - Freeze scenario bytes and rubric thresholds before producing baseline output. Do not inspect the holdout result during tuning, change only one instruction theme per iteration, and record any changed scenario as a new evaluation version rather than overwriting prior evidence.
  - Every critical requirement must pass. The accepted result must show no fact, quote, uncertainty, code-block, requested-format, or project-term drift; no new high-severity lint finding without rationale; adapted output no worse than baseline; and no material holdout regression.
  - Record actual model identifiers separately and do not compare scores across models as if they were one population. A natural-japanese self-score or same-session review is advisory and never the independent acceptance witness.
  - Do not modify provider policy to make the evaluation run. Human Copilot use supplies bounded external evidence; repository automation remains offline and the authoritative suites remain the existing lint-project-workflow and smoke commands.
  - Preserve existing project-owned AGENTS.md content during Copier update. The update may emit a deterministic warning and exact one-line routing suggestion, but it must never inject that line or treat warning absence as proof that Copilot loaded the skill.
  - Do not add or copy further japanese-tech-writing Gist prose. Preserve its existing adapted specification, source attribution, and project-specific requirements while making only the accepted priority and routing clarifications.
  - Keep the evaluation report compact and reviewable: bind scenario and output digests, retain the bounded output text needed to inspect facts and form, and reject missing critical results, duplicate scenario identities, mixed model identities, or a holdout marked as tuning input.
checked_summary_ja: プロジェクト規範を守る日本語文章作業をCopilot CLIから再現可能にする。

## Decisions

- Keep docs/agent/SPEC_JAPANESE_TECH_WRITING.md authoritative; adapted natural-japanese guidance and its lint are subordinate operational aids.
- Use short AGENTS.md routing plus .agents discovery bridges and managed skill bodies; do not add .github/copilot-instructions.md or concatenate the two rule sets into one prompt.
- Pin natural-japanese v1.5.0 at commit 21e632661a910bf97289c501089ad11eb8b4d85f, preserve MIT attribution, document local changes, and require an explicit review for any future upstream update.
- Use three application depths: a short final check for Japanese replies, reader-and-purpose planning plus one advisory lint pass for file work, and structure, terminology, reading-load, and independent-reader checks for important long-form prose.
- Apply user-requested style and form first, then facts, quotations, uncertainty and project terms, document structure, project Japanese policy, naturalness advice, and finally mechanical lint scores.
- Do not invent experience, motive, emotion, or certainty to make text sound human; retain personal voice only when supplied by the user or source.
- Keep japanese-tech-writing Gist material at its existing attribution boundary because no license for an additional verbatim copy was established.
- Keep deterministic lint diagnostic rather than corrective, dependency-free, bounded, and offline; context review decides whether each finding warrants a prose change.
- Use fixed scenarios and critical requirements, reserve the code-only scenario as holdout, and judge baseline versus adapted output in a fresh Copilot CLI session or by a human without using same-context self-review as independent evidence.
- Do not let automated repository scripts invoke Copilot, read credentials, or contact an external service; a human operates Copilot separately and commits only bounded nonsensitive evaluation evidence.

## Tasks

- [x] Add concise root and generated natural-japanese skill bodies, UI metadata, direct references, dependency-free advisory lint scripts, MIT license text, upstream tag and commit provenance, and .agents discovery bridges.
- [x] Define the three application depths, exact non-use and over-trigger boundaries, policy conflict order, document-heading choice, lint interpretation, and prohibition on fabricated human experience in the normative and operational files.
- [x] Route Japanese user communication from root and generated AGENTS, spec indexes, and write-for-reader while keeping root and template policy semantically aligned and SKILL.md files concise.
- [x] Register every managed source and generated path in ownership and Copier inventories, extend root/template and generated semantic checks, and preserve executable modes for the bundled lint script.
- [x] Extend Copier update validation and fixtures so project-owned AGENTS.md bytes are preserved and an absent Japanese-routing marker produces the exact manual integration instruction without becoming an unsafe automatic edit.
- [x] Implement a bounded offline evaluation packet and validator with immutable scenario identifiers, one median case, multiple edge cases, one tuning-blind holdout, critical requirements, output bounds, digests, model identity, and evaluator fields.
- [x] Have a human run baseline and adapted packets in fresh Copilot CLI sessions using nonsensitive fixtures, record results by model, independently compare them, then reveal and score the holdout once without tuning against its outcome.
- [x] Add regression coverage for bridge targets, frontmatter, provenance and license, root/template bytes, policy priority, three depths, advisory-only lint, code-block preservation, fact and uncertainty preservation, no code-only over-trigger, evaluation schema, and Copier update behavior.
- [x] Run focused checks, obtain independent review of the exact candidate and evaluation record, then run the authoritative suites exactly once and publish only the reviewed in-scope commit.

## Validation Notes

- Planning baseline: c9fa948ef85b858962e102dc76b69c0bb3367c9b in temp_project.
- Owner instruction: 「提案の方針でプランを作成せよ。」
- The owner accepted the prior proposal's normative hierarchy, AGENTS plus .agents integration, pinned adaptation, three application depths, conflict priority, fixed scenarios, holdout, root/template parity, and no merged prompt.
- The absent everyday Copilot model and absent user-provided awkward examples do not change implementation scope: record the actual model used, use the fixed nonsensitive cases, and add future user examples only in a separately versioned tuning and holdout split.
- Tier 2 applies because implementation changes root and generated policy, skill distribution, third-party adaptation, Copier ownership and update behavior, and validation coverage.
- Feasibility evidence establishes available mechanisms and a pinned source; it does not claim that the adapted skill, generated output, or empirical comparison has passed.
- No helper was used to author this plan; final policy judgment, plan admission, validation acceptance, commit, and publication remain parent-owned.
- During implementation, the generated validation parser rejected the new managed Skill helper in the Copier update lane. The owner approved extending the write scope to the generated `plan_validation_commands.py`; the root parser already admits the corresponding root path and requires no change.
- The planned root `docs/agent/SPEC_COPIER_ADOPTION.md` path does not exist. The required-spec reference therefore names the sole applicable generated adoption specification without changing its authority.
- Independent review used the initial two-review budget and the owner-authorized continuation epoch, exhausting the cumulative four-review maximum. The final review left one Medium finding: canonical routing text inside a fenced or explicitly non-operative example can suppress Copier's manual routing warning. Stop before authoritative validation, commit, archive, or publication and reconstruct the bounded routing-detection work.

- Reconstruction authorization: 「プランの修正と実装作業をせよ。」
- Continue in parent-direct mode from the exact promoted dirty snapshot; the remaining implementation change is bounded to canonical routing-line detection and its regression coverage.
- The reconstructed successor used an owner-authorized continuation epoch. Its final rereview found no remaining High or Medium findings after exact canonical-line, Markdown fence, indented-code, HTML-comment, and lint fence handling were corrected.
- Focused validation passed: `python3 scripts/check-root-agent-policy.py`, `python3 tests/test-natural-japanese.py`, `python3 scripts/check-copier-template.py`, and `tests/copier-update.sh`.
- Authoritative validation passed once on the accepted diff: `scripts/lint-project-workflow.sh` and `tests/smoke.sh`.
