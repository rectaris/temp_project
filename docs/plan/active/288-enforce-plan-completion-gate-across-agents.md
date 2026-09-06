# Enforce the plan completion gate across supported agent runtimes

status: in_progress
primary_invariant: On every repository-shipped completion boundary, the root or generated check-agent-completion.sh --plans-only command remains the only completion judgment: CI checks the committed tree, pre-commit checks the staged tree, and supported main-agent Stop hooks check the working tree without copying the completion predicates or claiming enforcement when a local layer is inactive.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"Run from a detached worktree at dd5525c, check-agent-completion.sh --plans-only exited 0 for six historical commits and exited 1 only for 0e4affe, naming the unmarked plan and the exact lifecycle command to run next."}
  - {"kind":"existing_mechanism","evidence":"check-agent-completion.sh already owns the plan-status and completion-evidence predicates; .project-agent-workflow/hooks/stop_review_gate.py already converts its result into the JSON decision used by the Codex Stop hook."}
  - {"kind":"bounded_prototype","evidence":"git checkout-index materialized the current index in a disposable local snapshot. The existing gate ran there, then rejected completion evidence added only to that snapshot while the unchanged working-tree invocation passed."}
  - {"kind":"bounded_prototype","evidence":"In disposable repositories on git 2.43.0, relative core.hooksPath=.githooks fired from the main and a linked worktree, while a missing hooks directory and a non-executable hook were silently ignored and the commit succeeded."}
  - {"kind":"existing_mechanism","evidence":"GitHub's hooks reference documents repository .github/hooks JSON, agentStop block decisions, stop_hook_active, stdout JSON on exit 0, and fail-open non-zero command-hook errors; current tests already exercise the shared Stop adapter."}
  - {"kind":"existing_mechanism","evidence":"check-copier-template.py already enforces root/template bytes and file modes, copier_inventory.py owns generated paths, and tests/copier-update.sh already exercises an isolated update that preserves project-owned files."}
completion_conditions:
  - Root CI and the generated workflow invoke the resolved completion gate with --plans-only against their checked-out commit tree, and deterministic fixtures reject a completed in_progress plan without rejecting sampled unfinished history states.
  - The committed pre-commit hook expands the exact index into a disposable directory, runs the resolved gate there, blocks on a non-zero result or absent gate, and works from a linked worktree.
  - The root mandatory validation script exits non-zero with the exact activation command when the shipped hook is not selected, but emits no activation error outside a work tree, under CI, or without the shipped hook.
  - The existing shared Stop adapter serves Codex Stop and Copilot agentStop, returns one valid block object with exit 0 for a missing or failing gate, preserves a useful diagnostic, and does not block again when stop_hook_active is true.
  - Copier inventory, root/template parity, executable-bit, and complete mode checks cover the Git hook, Copilot hook configuration, and shared Stop adapter.
  - The generated workflow watches .githooks and .github/hooks changes, and a generated project receives both hook surfaces without the root-only activation detector changing its ordinary local validation behavior.
  - Regression fixtures cover staged-versus-working-tree divergence, ready-to-archive finalization, a missing gate, inactive hooks configuration, linked-worktree commit, non-executable hook, and the explicit --no-verify bypass boundary.
completion_witness_map:
  - {"condition_sha256":"sha256:9c0564048440e548c8bfc9cd31be22e4ad1b624de91f10ceee907e4e73c254fe","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:cf1aab8ea4c31e1e82cbee3520654e76116e1e798780fca6ce9c0af0a55f6e00","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:7944f07e0f333d519d1643b20844518fd9229c91a3e3b4a9dcd72d5d2ef9850d","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:df92720a9747966e1c77ad77306aaf8b5d3c5e9c8edc538b2b1cbaa002fc4854","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:f4b4342ca61bb2014a3a5e884113bc809599ac1873572937bb6bbf9ba7b2d295","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:8a3c95d8cc432730bab1633d8d3938403df24964c3008abe92c150eb157172b9","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:3d9e959ba2f3588cf9f0e3d9308904356113fd5b22a46aad6537537ccfbba040","witness":"tests/root-plan-lifecycle.sh"}
write_scope:
  - .githooks/pre-commit
  - template/.githooks/pre-commit
  - .github/hooks/plan-lifecycle.json
  - template/.github/hooks/plan-lifecycle.json
  - .project-agent-workflow/hooks/stop_review_gate.py
  - template/.project-agent-workflow/hooks/stop_review_gate.py
  - scripts/lint-project-workflow.sh
  - .github/workflows/ci.yml
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - copier.yml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/root-plan-lifecycle.sh
  - tests/validation_tools/generated.py
  - tests/hooks/gates.py
  - tests/hooks/support.py
  - tests/smoke.sh
  - tests/copier-update.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/check-agent-completion.sh
  - template/.project-agent-workflow/scripts/check-agent-completion.sh
  - scripts/complete-plan.sh
  - .codex/hooks.json
  - template/.codex/hooks.json.jinja
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - tests/root-plan-lifecycle.sh
  - python3 tests/test-hooks.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/check-root-agent-policy.py
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - tests/copier-update.sh --require-copier
acceptance:
  - Make the repository-shipped root and generated CI workflows fail when their checked-out commit tree contains an in_progress plan with complete task and Validation Notes evidence, without rejecting the sampled unfinished states from current history.
  - Make the configured pre-commit hook judge the exact staged tree through the existing completion gate, fail closed when the gate is absent, and behave the same in the main and linked worktrees.
  - Make root mandatory validation report an inactive core.hooksPath with the exact activation command, without mutating Git configuration or reporting it under CI, outside a work tree, or when the hook is not shipped.
  - Reuse one Stop adapter for the existing Codex Stop hook and the repository Copilot agentStop hook, returning one bounded continuation prompt for a missing or failing gate without attaching plan-finalization authority to subagents.
  - Distribute the added Git and Copilot hook surfaces under inventory, root/template parity, executable-bit, mode, and generated-workflow path-filter checks.
  - Keep fresh generated-project smoke scenarios passing with the hook files installed and no generated activation detector or automatic core.hooksPath write.
  - Preserve project-owned product code, policy, configuration, plan history, and validation behavior during an actual Copier update that installs the managed hook artifacts without writing core.hooksPath.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:6e7a92d5c55d77c6fc09091f78a82349d6f731b6a05a447ad59ea51f4ae7dc6d","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:3c8e78b436de614173b95038497c770908fbc7e19a8aef9e304669b0d2ed3ffe","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:789b03f9c7c8dcdd42dda6753a56b0b0953a356e9cec3f370ddfcd334f0537bf","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:e7b3d127ff234c92baca7e866dc2e4abb380b2c674fe26923f7f9bff1acf33d4","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:786dfdbd23f0e8ae2810e0588022dbd60187713e5ef1669a0cc1218a23c5efab","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:fc366064c9056f1df50414a7ddfdf3d255615fa8a241061ca36981215c49c2b3","stage":"authoritative","witness":"tests/smoke.sh","authoritative_only_reason":"The fresh generated-project lifecycle and workflow interaction is exercised by the complete Copier-generated smoke scenarios; the focused inventory and hook fixtures run first but do not establish the integrated generated result."}
  - {"acceptance_sha256":"sha256:7da53a5d0ae15805231dfd9c37b26c563108970dd14a2957bce0d93bceca9d23","stage":"authoritative","witness":"tests/copier-update.sh --require-copier","authoritative_only_reason":"Only the isolated before-update and after-update Copier transaction establishes preservation of existing project-owned files while installing newly managed hook artifacts; narrower inventory and fresh-generation checks run first but do not cross this update boundary."}
integration_gates:
  - Keep exactly one completion judgment. Every CI, Git, and main-agent layer calls the root or generated check-agent-completion.sh --plans-only command; no adapter reimplements task-checkbox, Validation Notes, plan-index, or lifecycle predicates.
  - Bind each invocation to the view owned by its boundary: CI uses the checked-out commit tree, pre-commit expands the complete index with git checkout-index into a disposable directory, and main-agent Stop checks the current working tree.
  - The pre-commit hook must not inspect unstaged plan bytes, mutate the index, create a commit, run lifecycle transitions, or copy only selected plan paths. Remove its disposable snapshot on normal exit and signals.
  - Resolve the gate inside the selected tree as .project-agent-workflow/scripts/check-agent-completion.sh first and scripts/check-agent-completion.sh second, matching the existing Stop adapter order, and run it from that tree's top level.
  - Ship .githooks/pre-commit with mode 755 on both sides, because Git records the executable bit and silently ignores a non-executable hook with only a hint.
  - Activate hooks only with the documented relative value .githooks so one main-clone setting applies to linked worktrees. Never set, overwrite, or unset core.hooksPath from a script, hook, Copier task, or migration.
  - Keep the activation detector in root scripts/lint-project-workflow.sh only. Compare the effective value exactly, print git config core.hooksPath .githooks, and skip the check before configuration reads in CI, non-work-tree, and hook-absent contexts.
  - Configure Copilot through version-1 .github/hooks JSON and invoke the existing .project-agent-workflow/hooks/stop_review_gate.py used by Codex. A missing gate, non-zero gate result, or empty gate diagnostic emits exactly one valid block object on stdout and exits zero; stop_hook_active=true emits an empty decision.
  - Treat the existing Codex Stop event and the new Copilot agentStop event as the supported main-agent surfaces in this plan. Do not configure subagentStop: helpers return advisory evidence and cannot own lifecycle, commits, or completion reporting.
  - Keep the hook commands local and deterministic: no network access, external-service write, credential read, environment dump, or secret persistence. A repository-controlled hook is not a trust boundary for untrusted checkout contents, so do not claim protection against a branch that replaces the hook itself.
  - Support the existing POSIX shell execution environment used by the completion scripts and Linux CI. Do not claim a native Windows PowerShell completion gate in this plan.
  - Keep CI as the repository-shipped enforcement boundary and local hooks as bounded fast feedback. Add .githooks/** and .github/hooks/** to the generated workflow path filters; do not claim that repository files configure external branch-protection requirements.
  - Preserve the existing gate judgment and lifecycle commands. A ready_to_archive snapshot must direct the user to finalization, and a fully finalized staged tree must be committable without a hook exception or bypass.
  - Keep generated projects free of the root activation detector. Use Copier's post-copy message and aligned plan-workflow specifications for the activation command, but do not add an automatic task or migration.
  - Add root/generated smoke and non-destructive Copier update coverage. Preserve project-owned code, policy, configuration, plan history, validation behavior, and every existing test; stop on conflicts, rejection files, or unclassified tracked-file deletion.
checked_summary_ja: commit 済みツリー、ステージ済みツリー、対応する main-agent の作業ツリーから同じ完了判定を呼び、各境界の保証範囲を越えずに未処理のプラン完了を検出する。

## Decisions

- Keep `scripts/check-agent-completion.sh --plans-only` and its generated counterpart as the only plan-completion judgment.
- Evaluate the tree owned by each boundary: the committed tree in CI, the complete staged index in pre-commit, and the working tree in supported main-agent Stop hooks.
- Reuse `.project-agent-workflow/hooks/stop_review_gate.py` for Codex Stop and Copilot `agentStop`; do not add a second result-to-JSON wrapper.
- Return at most one forced main-agent continuation by honoring `stop_hook_active`, and do not attach this completion gate to `subagentStop`.
- Treat CI as the repository-shipped enforcement boundary and local hooks as fast feedback because local configuration and `--no-verify` remain user-controllable.
- Distribute `.githooks/` with a relative manual `core.hooksPath`; report an inactive setting in root validation and never change it automatically.
- Keep the root-only activation detector out of generated projects while installing the hook surfaces, activation guidance, CI check, and update-preservation coverage.

## Tasks

- [ ] Add failing fixtures for committed completion evidence, staged-versus-working-tree divergence, ready-to-archive finalization, a missing gate, inactive configuration, linked-worktree commit, a non-executable hook, and `--no-verify`.
- [ ] Add the root and template pre-commit hook that expands the complete index into a disposable snapshot and delegates to the gate resolved inside that snapshot.
- [ ] Extend the aligned shared Stop adapter for fail-closed missing-gate output, non-empty fallback diagnostics, one-continuation self-limiting, and both Codex and Copilot configuration fixtures.
- [ ] Add the root-only activation detector with exact work-tree, shipped-hook, CI, and effective-value guards and no Git configuration write.
- [ ] Add the completion command to root and generated CI and extend generated path filters for both managed hook surfaces.
- [ ] Register and mirror every added artifact, enforcing root/template bytes, executable bits, and complete modes.
- [ ] Record the manual activation command and bounded layer guarantees in Copier's post-copy message and the aligned plan-workflow specifications.
- [ ] Extend fresh-generation smoke and actual Copier update fixtures, including proof that project-owned files and Git configuration remain unchanged.
- [ ] Review the exact implementation and critical invariants independently, run every focused command, then run the authoritative suite once for an otherwise acceptable candidate.

## Validation Notes

- Initial planning baseline: `16514a545bafe5b873947218eaf229b6eb0a47f6` in `temp_project`.
- Polish baseline: `85fac4421a23ac3b4e2ffc87a5214cffedc8ef92` in `temp_project`.
- Owner directions: 「提案の方針で docs/plan/active にプランを作成せよ。」 and 「docs/plan/active/288-enforce-plan-completion-gate-across-agents.md についてプランのブラッシュアップをせよ。」 The first approved the three-layer design; the second authorizes this plan-only clarification of the tree views, supported runtimes, security route, validation witnesses, and Copier-update boundary.
- The reproduced defect and Git behavior prototypes used detached or disposable worktrees, repositories, and local snapshots and changed no tracked repository file. Feasibility evidence does not claim that future completion witnesses already pass.
- Full decision audits are local evidence under `.agent-artifacts/decision-audits/plan-lifecycle-completion-gate/`; only accepted executable decisions appear here.
- The current official GitHub Copilot hooks reference was rechecked on 2026-09-06 for `.github/hooks/*.json`, `agentStop`, block decision output, command-hook exit behavior, `stop_hook_active`, and the runaway guard. Runtime behavior remains bounded by that external contract.
- Local reach is bounded. `git commit --no-verify`, a manually changed `core.hooksPath`, disabled repository hooks, and a fresh clone before activation remain outside local enforcement; repository files also do not configure GitHub branch protection.
- The committed hooks execute repository-controlled code with the caller's local environment. This plan adds no network, external-write, credential-read, or secret-persistence behavior and makes no guarantee for an untrusted branch that replaces the hook; native Windows PowerShell execution is also outside this POSIX-shell release.
- A main-agent Stop hook requests at most one continuation. Subagents remain advisory and the main session retains plan lifecycle, validation acceptance, commits, and final reporting.
- No performance or time saving is claimed. Implementation must establish only the declared tree-specific reachability, fail-closed adapter behavior, and non-destructive distribution.
- Plan-polish validation passed: `python3 scripts/check-root-agent-policy.py`, `python3 tests/test-validation-tools.py`, `scripts/lint-project-workflow.sh`, and `tests/smoke.sh` exited 0. Smoke exercised generated-project scenarios; optional GitHub Actions lint was skipped because `actionlint` was unavailable. These results validate this plan update and the existing repository, not the future implementation witnesses.
- The earlier read-only research helper had no write scope. This polish turn used no helper; the main session verified repository behavior and current official hook semantics and owns the plan update, validation, commit, and report.
