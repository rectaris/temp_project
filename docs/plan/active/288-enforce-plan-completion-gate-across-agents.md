# Enforce the plan completion gate across agent runtimes

status: in_progress
primary_invariant: The existing completion gate keeps one judgment implementation, and every added layer reaches that same judgment through a thin adapter that either blocks with the gate's own next-step message or is itself reported as inactive, so no runtime, clone, or commit path can reach a reported completion while an evidently finished plan is still unmarked.
task_types:
  - template_workflow
  - planning_docs
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"Run from a detached worktree at dd5525c, check-agent-completion.sh --plans-only exited 0 for six historical commits and exited 1 only for 0e4affe, naming the unmarked plan and the exact complete-plan.sh command to run next."}
  - {"kind":"existing_mechanism","evidence":"check-agent-completion.sh already reads docs/plan/plan.md, compares index and manifest status, calls complete-plan.sh --check-completion-evidence, and prints a Next line; stop_review_gate.py already resolves the generated path before the root path."}
  - {"kind":"bounded_prototype","evidence":"In disposable repositories on git 2.43.0, a relative core.hooksPath fired the committed hook from both the main and a linked worktree, while a missing hooks directory and a non-executable hook were both silently ignored and the commit succeeded."}
  - {"kind":"existing_mechanism","evidence":"check-copier-template.py already enforces executable bits and root/template mode equality with fail(\"... must be executable\"), and copier_inventory.py already registers .codex/hooks paths on both the template and generated sides."}
completion_conditions:
  - Root and generated CI run the completion gate with --plans-only, so a pushed tip whose active index and plan manifest both report in_progress while completion evidence is present fails the required checks.
  - A committed pre-commit hook delegates to the resolved completion gate, blocks the commit on a non-zero gate result, refuses to run when the gate file is absent, and resolves the generated tooling path before the root path.
  - The root mandatory validation script reports an unactivated hooks configuration with the exact activation command and exits non-zero, while skipping that report outside a work tree, without a shipped hook, and under CI.
  - A repository-level agentStop hook configuration reaches the same gate through a wrapper that exits zero and emits a block decision carrying the gate output, so a forced continuation names the pending lifecycle command.
  - Copier inventory, parity, executable-bit and mode checks cover every added hook, wrapper and configuration file on both the template and generated sides.
  - Generated projects receive the hook, wrapper and configuration without any activation detector, and the generated smoke scenarios keep passing unchanged.
  - Regression fixtures cover an unmarked completed plan, an absent gate file, an unactivated hooks configuration, a linked-worktree commit, and a non-executable hook.
completion_witness_map:
  - {"condition_sha256":"sha256:84b3f5803a6f13c5b0f717b98a66ab7dfd1c267043f59b646ae5437a24dcd509","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:fa947e05e30648289f325f02153f686ad29f12b5dc329f5c6b1dbbfb8b510537","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:9960e2708cbeef11e44f218592b60f3448fefe0ea2caa3a884a20553671ab02b","witness":"tests/root-plan-lifecycle.sh"}
  - {"condition_sha256":"sha256:b0e634b3268d5fe5a91330c756abf73e0fda338c62917265c59df25995ac0f70","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:db1a699ed49960b175256f9c886fad808ffd5a7a15c114cde0b26b0972c44dad","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:02455808ef0bf6276beb0785a05fa7d2251bb17bc81163d5b10e6091d2add7ca","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a786a37d39c210e251391527836f2e97a8bed0eec9b3cdf35a9e192044a3a3f8","witness":"tests/root-plan-lifecycle.sh"}
write_scope:
  - .githooks/pre-commit
  - template/.githooks/pre-commit
  - .github/hooks/plan-lifecycle.json
  - template/.github/hooks/plan-lifecycle.json
  - scripts/agent-stop-completion-gate.sh
  - template/.project-agent-workflow/scripts/agent-stop-completion-gate.sh
  - scripts/lint-project-workflow.sh
  - .github/workflows/ci.yml
  - template/.github/workflows/project-agent-workflow.yml
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - copier.yml
  - AGENTS.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/root-plan-lifecycle.sh
  - tests/validation_tools/generated.py
  - tests/test-hooks.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/check-agent-completion.sh
  - scripts/complete-plan.sh
  - template/.project-agent-workflow/hooks/stop_review_gate.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
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
acceptance:
  - Make required CI on both the root repository and generated projects fail a pushed tip that reports an unmarked completed plan, without failing any state the current history already produces.
  - Ship an activated-by-configuration pre-commit hook that delegates to the existing completion gate, fails closed when that gate is missing, and works from linked worktrees.
  - Report an unactivated hooks configuration from the root mandatory validation command with the exact activation command, and keep that report out of CI, non-work-tree and hook-less contexts.
  - Reach the same completion gate from a repository-level agentStop hook using a wrapper whose exit status cannot silently disable the block.
  - Distribute every added file to generated projects under existing inventory, parity and executable-bit checks while leaving generated smoke behavior unchanged.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:409ff26dd4def81268c8eaa4e3d9abd780dcd8fec667a04685e5e798a0db2335","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:f28dcaa101a83d3b5698235063cdf82558b9e53612a38f04180d6c630e7aa7de","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:88e5c8113a4ecc86acd345934fc92751dae8b034923379d21c737cf10e9cde46","stage":"focused","witness":"tests/root-plan-lifecycle.sh"}
  - {"acceptance_sha256":"sha256:d9683c9ab59a2de03f6c2b79b2ad70411fb9c78a68fe012e24963ef8d8a56505","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:ef4ef68ea59bb4c29e28b28124d43481b7db740be54b92ca90f1665742233c90","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Keep exactly one judgment implementation. Every layer calls check-agent-completion.sh --plans-only; no layer reimplements the unchecked-task or Validation-Notes predicates.
  - Resolve the gate as .project-agent-workflow/scripts/check-agent-completion.sh first and scripts/check-agent-completion.sh second, matching the existing stop_review_gate.py order, and run it from the worktree top level reported by git rev-parse --show-toplevel.
  - Ship .githooks/pre-commit with mode 755 on both sides, because git records the executable bit and silently ignores a non-executable hook with only a hint.
  - Activate hooks with the relative value .githooks so a single main-clone activation covers every present and future linked worktree. Do not set core.hooksPath automatically from any script or Copier task.
  - Emit the agentStop decision as a single JSON object on stdout with exit status zero, because Copilot CLI treats a non-zero agentStop exit as fail-open and would ignore the block.
  - Keep the activation detector in scripts/lint-project-workflow.sh only. Generated projects receive the hook files and written activation guidance but no detector, so generated smoke projects created by Copier do not fail for being unactivated.
  - Do not weaken or bypass the existing gate. The layers add reach, not new tolerance, and the gate output remains the single source of the next-step instruction.
checked_summary_ja: 完了ゲートを CI、Git フック、エージェント実行環境の三層から同じ判定へ到達させ、未マークの完了プランを見逃さないようにする。

## Decisions

- The concrete target is `scripts/check-agent-completion.sh` and the paths that can reach it. Its judgment is unchanged; only its reachability changes.
- Distribute Git hooks as a committed `.githooks/` directory activated by a relative `core.hooksPath`. Reject symlink installation, which fails in linked worktrees, and the `pre-commit` framework, which adds a dependency and is mutually exclusive with `core.hooksPath`.
- Detect an unactivated hooks configuration and print the fix; never set it automatically, in either the root repository or a Copier task.
- Treat CI as the enforced invariant and the local layers as fast feedback, because `--no-verify` and manual unsetting cannot be prevented locally.
- Keep the activation detector out of generated projects so Copier-generated smoke fixtures stay valid.
- Record in the plan that `git commit --no-verify`, a manually unset `core.hooksPath`, and agent harnesses that disable hooks remain outside local enforcement.

## Tasks

- [ ] Add failing fixtures for an unmarked completed plan, an absent gate file, an unactivated hooks configuration, a linked-worktree commit and a non-executable hook.
- [ ] Add the committed pre-commit hook and the agentStop wrapper and configuration on the root side, with the shared gate resolution order and fail-closed behavior.
- [ ] Add the activation detector to the root mandatory validation script with its work-tree, shipped-hook and CI guards.
- [ ] Add the completion gate step to root CI and to the generated-project workflow.
- [ ] Mirror every added file into the template, register it in the Copier inventory, and extend parity, executable-bit and mode checks.
- [ ] Record the activation command and the layer boundaries in the aligned policy and specification files.
- [ ] Run focused validation, obtain independent review, and run the unchanged authoritative suite once for an acceptable candidate.

## Validation Notes

- Planning baseline: `16514a5` in `temp_project`.
- Owner direction: 「提案の方針で docs/plan/active にプランを作成せよ。」 This approves the three-layer design and the recommended answers to the open questions on directory name, generated-project activation and the treatment of `--no-verify`. This turn creates the plan only and does not implement it.
- The reproduced defect and the Git behavior prototypes used disposable worktrees and temporary repositories and changed no repository file. Feasibility evidence is not a claim that future completion witnesses already pass.
- The full decision audit is local evidence under `.agent-artifacts/decision-audits/plan-lifecycle-completion-gate/`; only the accepted decisions appear above.
- Layer reach is bounded and stated rather than claimed as complete. `git commit --no-verify`, a manually unset `core.hooksPath` and an agent harness that disables hooks all remain outside local enforcement, and a fresh clone stays unprotected until the detector runs.
- The `agentStop` continuation is bounded by the runtime: after eight consecutive block decisions the CLI ends the turn regardless, so this layer is a bounded correction prompt and not an absolute stop.
- No performance or time saving is claimed. The implementation must establish only the declared reachability and fail-closed behavior.
- A read-only research helper supplied the external distribution evidence with no write scope; the parent verified the Git behavior claims independently in disposable repositories and owns acceptance.
