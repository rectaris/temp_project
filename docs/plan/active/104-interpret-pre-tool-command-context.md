# Interpret actual command context before requiring a task worktree

status: in_progress
primary_invariant: The pre-tool worktree decision uses a bounded recognized invocation and its effective repository directory; a lifecycle filename used only as data never becomes write classification or authority.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The hook searches arbitrary command positions for restructure-plan.py; the preceding investigation observed a read-only wc invocation refused for that filename alone.","kind":"existing_mechanism"}
  - {"evidence":"Both hooks call the shared guard, whose require_task_worktree accepts cwd; the hook supplies only action. Existing hook fixtures create source and bound worktrees.","kind":"existing_mechanism"}
  - {"evidence":"The execution-tool interface exposes workdir and the hook parses tool_input and arguments objects. An absent field cannot establish an external runtime directory.","kind":"existing_mechanism"}
completion_conditions:
  - Reading or counting a lifecycle script as data does not trigger the worktree write guard, while supported lifecycle mutations and Git writes still require the valid bound worktree.
  - Recognized tool workdir and supported Git -C options select the effective directory; conflicting or malformed context is rejected without a more permissive repository fallback.
  - Existing read-only lifecycle modes remain exempt; generic Python and shell text are never certified read-only, and existing destructive-command and secret protections remain unchanged.
  - Root and generated hooks use one shared interpreter distributed by the template inventory without changing project-owned configuration.
completion_witness_map:
  - {"condition_sha256":"sha256:639974b33514ee85859a502260dc968e530bef5fce9cbc0b3f050c1f4388cb4c","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:0243c89c86f86a67df4bce2dd6fe927b926389fcc5745dd7723d70278d898a78","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:9c55c43f300180055a6557ae9676c2eb39f679fe53870a8400dbaa873a39ab6b","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:35f9b5e36aa1020b3abec7caf87b3689b4e6b1c88f3c190ad199a48c9f34d759","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/scripts/tool_command_context.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/hooks/gates.py
  - tests/hooks/support.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/project_workflow/worktree_guard.py
  - tests/test-hooks.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Reading or counting a lifecycle script as data does not trigger the worktree write guard, while supported lifecycle mutations and Git writes still require the valid bound worktree.
  - Recognized tool workdir and supported Git -C options select the effective directory; conflicting or malformed context is rejected without a more permissive repository fallback.
  - Existing read-only lifecycle modes remain exempt; generic Python and shell text are never certified read-only, and existing destructive-command and secret protections remain unchanged.
  - Root and generated hooks use one shared interpreter distributed by the template inventory without changing project-owned configuration.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:639974b33514ee85859a502260dc968e530bef5fce9cbc0b3f050c1f4388cb4c","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:0243c89c86f86a67df4bce2dd6fe927b926389fcc5745dd7723d70278d898a78","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:9c55c43f300180055a6557ae9676c2eb39f679fe53870a8400dbaa873a39ab6b","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:35f9b5e36aa1020b3abec7caf87b3689b4e6b1c88f3c190ad199a48c9f34d759","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after this backlog plan is selected for implementation and published as active; use its exact bound task worktree.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - No shell evaluation, command execution, interpreter-wide allowlist, new runtime protocol or disabled guard.
  - External forwarding beyond an explicit supported workdir field is outside scope. A missing field remains an integration limitation, not a numbered investigation plan.
checked_summary_ja: 実行対象と実行場所を区別し、参照だけの操作を誤って止めない。

## Decisions

- Extract one shared interpreter for explicitly supported invocation forms. Do not build a general shell execution model.
- Recognize ordinary Git commands and a single Python or shell interpreter launching a named lifecycle script, including existing read-only modes. Filenames in data arguments and Python program bodies are not nested invocations.
- Read workdir only from a supported execution-tool argument object; reconcile duplicate containers and supported Git -C options. Resolve relative paths against the established invocation base.
- When execution-directory metadata is absent, retain the hook process directory and name that limitation. Do not infer external workdir from prompts or arbitrary strings.
- Keep authoritative checks in lifecycle commands and pre-commit. An unrecognized command is not certified read-only or authorized to bypass those checks.

## Tasks

- [ ] Add regressions for wc/cat/rg lifecycle filenames, inline Python data, actual script invocations and read-only modes.
- [ ] Extract shared invocation/context parsing and call it from both hooks without moving destructive and secret rule authority.
- [ ] Cover argument containers, missing/relative/conflicting workdir, Git -C and source-versus-bound repositories with existing hook fixtures.
- [ ] Review the supported-form table against actual payload evidence; report missing runtime forwarding rather than claim session migration.
- [ ] Run focused checks, independent review and one authoritative suite for the accepted patch.

## Validation Notes

- Planning baseline: b3e300888412f7e9c2fb243435da4cb4082f5135 in temp_project.
- Owner instruction: 提案の方針でプランを作成せよ。変更点が多い場合は複数のプランとして作成せよ。手続きとして削減するべき部分をまとめたり、スキル化、関数化するべき部分など、改善できる部分をまとめよ。
- This instruction authorizes plan authoring, not implementation or reopening a stopped run. This is ordinary backlog work, not a reconstruction successor.
- See docs/plan/backlog/README.md for procedure reductions, existing-plan reuse and implementation order. Full decision audit stays in local development-process-planning evidence.
- The shared authoring checker derives correspondence and digests; the parent reviews witness semantics. No measured productivity saving is claimed.
