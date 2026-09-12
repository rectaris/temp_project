# Record template improvement evidence in generated repositories

status: in_progress
implementation_mode: parent_direct
primary_invariant: Each recorded improvement preserves its observed evidence and uncertainty in project-owned files without changing the originating product task or granting external effects.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"human-report.py validates bounded structured reports and writes project-owned artifacts. worktree_guard.py and manage-plan-worktrees.py already bind separate direct tasks and publish them locally.","kind":"existing_mechanism"}
  - {"evidence":"copier.yml already preserves docs/agent/** and ships managed policy through spec-index.yaml.jinja. tests/prepare-smoke-source.py renders current source bytes into disposable fixtures.","kind":"existing_mechanism"}
completion_conditions:
  - Both CLI layouts validate bounded non-sensitive records, reject suspected secrets and conflicting record bytes, preserve unknown provenance, and make identical retries a no-op.
  - Routing and config expose local automatic preparation and disabled mode; actual report writes require their own valid task binding, and root/template implementations remain aligned.
  - The template checker enforces the declared generic root/generated counterparts and excludes actual project-owned runtime records from the generated inventory.
completion_witness_map:
  - {"condition_sha256":"sha256:f80a6bb941efc2e4015e2bc94d80438459793b0f80752ca2bb8a22f8ec8f573d","witness":"python3 tests/test-template-feedback.py"}
  - {"condition_sha256":"sha256:92458b416e4cc2df0ff7ca857c9221f6b2be66c8f062c3a38885c6e09d5e0563","witness":"python3 tests/test-template-feedback.py"}
  - {"condition_sha256":"sha256:bb9d23bec50c137151ca2571d4a6acb161ecc86a67a2c1ab245b28641a2f2002","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/template-feedback.py
  - template/.project-agent-workflow/scripts/template-feedback.py
  - docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - template/.project-agent-workflow/docs/agent/SPEC_TEMPLATE_FEEDBACK.md
  - tests/test-template-feedback.py
  - AGENTS.md
  - template/.project-agent-workflow/AGENTS.md.jinja
  - docs/agent/spec-index.yaml
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - docs/agent/template-feedback.json
  - template/docs/agent/template-feedback.json.jinja
  - copier.yml
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - scripts/project_workflow/worktree_guard.py
  - scripts/manage-plan-worktrees.py
  - template/.project-agent-workflow/scripts/human-report.py
  - template/.project-agent-workflow/ownership.yaml
  - tests/prepare-smoke-source.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - references/validation.md
focused_validation:
  - python3 tests/test-template-feedback.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A generated project can record expected and observed behavior, impact, evidence, requested outcome, temporary workarounds and template provenance without inventing missing facts.
  - For the declared trigger, no-finding and disabled scenarios, policy directs local draft preparation or no-op; reviewed report persistence preserves task boundaries and introduces no network effect or Stop veto.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:c537f00e3200eefb9790bd42a5b5654947b41b0295846fccdef83b9f2f130a00","stage":"focused","witness":"python3 tests/test-template-feedback.py"}
  - {"acceptance_sha256":"sha256:a15c4183523d575671fea098083347b635f7342106eb9cccab62f2177cc270cd","stage":"focused","witness":"python3 tests/test-template-feedback.py"}
integration_gates:
  - Before implementation, prepare this exact published active plan worktree and initialize the parent-owned execution ledger and reviewer registry. Keep bounded parent-direct scope, exact-target adversarial preflight, independent review budgets, focused witnesses and the unchanged authoritative suite; a stopped state remains stopped under the existing policy.
checked_summary_ja: コピー先で見つかったテンプレートの改善案を根拠付きで記録する。

## Decisions

- The owner approved the preceding local-first proposal and requested plan authoring only. Keep this plan in backlog until selected for implementation; do not start implementation in its authoring task.
- Use bounded parent implementation with independent read-only review because the single evidence-preservation invariant spans policy, write guards and validation registration. Tier 2 reflects the new governed write surface; existing security and validation authority stay unchanged.
- Use schema version 1, a stable project alias plus report id, template source alias and exact revision when available, expected/observed behavior, impact, bounded evidence summaries, desired behavior, workaround and explicit attribution certainty. Unknown revision or cause is a valid explicit value.
- Require strict JSON shape and size bounds. Use check then record with the exact checked-input digest, derive confined paths, reject unsafe links and identity/content conflicts, and preserve immutable records. A correction uses a new id with an explicit supersedes reference.
- At task wrap-up, the agent prepares a local ignored draft only for an observed template workaround, contradiction, repeated obstacle or concrete reusable improvement. Evidence excerpts are selected explicitly; do not scan entire logs, environment files or arbitrary project trees. No-finding and disabled paths are no-ops.
- Before persisting any draft or report, select only non-sensitive evidence classes: agent-written paraphrases, synthetic reproduction steps and reviewed relative code/change references. The parent reviews the exact content before check/record; reject suspected credentials or private data. Do not copy raw logs or rely on automatic redaction as proof of safety.
- Persist reviewed records under docs/template-feedback/ through a separately prepared direct task after the product task permits publication. Use the shared worktree guard before the first repository effect, commit and publish only report files. A blocked report save leaves the draft pending and cannot claim a saved record or block the product conversation.
- Expose template_feedback_mode in copier.yml with agent_select_local as default and disabled as opt-out, rendering a project-owned docs/agent/template-feedback.json. Apply the existing docs/agent preservation rule on update. Root configuration uses its own explicit project alias, never a copied downstream identity.
- Generic policy and deterministic tooling are mirrored; actual records remain project owned and are never shipped in template/. Do not introduce a skill, scheduler, Stop-hook write, external sender or external-access policy change. Automatic preparation is agent behavior; deterministic checks do not prove every agent will detect every useful improvement.

## Tasks

- [ ] Implement bounded check/record commands and safe idempotent storage using the existing direct-task guard.
- [ ] Add local mode configuration and root/generated task routing, including pending-draft recovery after ordinary task publication.
- [ ] Add root/generated cases for schema, identity, suspected-sensitive excerpts and task boundaries. Check named trigger/no-finding/disabled examples through deterministic routing fixtures and independent semantic review; do not claim universal real-task detection. Register files and parity without weakening checks.
- [ ] Exercise a generated local fixture and obtain independent semantic review of the trigger examples before focused and authoritative validation.

## Validation Notes

- Owner instruction: 提案の方針のプランを作成せよ。 Accepted proposal stays local; automated external delivery is a later separately authorized extension.
- This record authorizes only its bounded future implementation after backlog promotion and plan publication. No implementation tests have run during plan authoring.
- Independent plan review required bounded agent-behavior claims, non-sensitive evidence review, data-only handling of imported instructions and verification of real owner adoption. Those boundaries are explicit tasks and negative cases in this plan chain.
