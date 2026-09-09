# Complete bounded pre-tool command context interpretation

status: checked
primary_invariant: The pre-tool worktree decision uses a bounded recognized invocation and its effective repository directory; a lifecycle filename used only as data never becomes write classification or authority, and an invocation this interpreter cannot read falls back to the previous conservative classification.
replan_sources:
  - docs/plan/active/104-interpret-pre-tool-command-context.md
replan_contract: docs/plan/replanned/contracts/104-complete-pre-tool-command-context.json
successor_plans:
  - docs/plan/active/301-complete-pre-tool-command-context.md
inherited_acceptance_digests:
  - sha256:639974b33514ee85859a502260dc968e530bef5fce9cbc0b3f050c1f4388cb4c
  - sha256:0243c89c86f86a67df4bce2dd6fe927b926389fcc5745dd7723d70278d898a78
  - sha256:9c55c43f300180055a6557ae9676c2eb39f679fe53870a8400dbaa873a39ab6b
  - sha256:35f9b5e36aa1020b3abec7caf87b3689b4e6b1c88f3c190ad199a48c9f34d759
integration_source_ids:
  - 104
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
implementation_mode: parent_direct
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"Differential comparison of the previous WRITE_COMMANDS patterns against the preserved candidate reproduced seven wrapper, redirection and command-runner forms of a lifecycle invocation that the previous classifier refused and the candidate allows."}
  - {"kind":"bounded_prototype","evidence":"A prototype outside the repository added a distinct unrecognized answer for an option, IO number or command runner in program position and restored all seven forms while keeping the recorded read-only exemptions and every genuine write refused."}
  - {"kind":"existing_mechanism","evidence":"The promoted candidate already passes python3 tests/test-hooks.py with 85 tests, python3 scripts/check-copier-template.py and scripts/lint-project-workflow.sh, so only the unrecognized-form answer remains open."}
completion_conditions:
  - Reading or counting a lifecycle script as data does not trigger the worktree write guard, while supported lifecycle mutations and Git writes still require the valid bound worktree.
  - Recognized tool workdir and supported Git -C options select the effective directory; conflicting or malformed context is rejected without a more permissive repository fallback.
  - Existing read-only lifecycle modes remain exempt; generic Python and shell text are never certified read-only, and existing destructive-command and secret protections remain unchanged.
  - Root and generated hooks use one shared interpreter distributed by the template inventory without changing project-owned configuration.
  - An invocation form the interpreter cannot read is answered as unrecognized and reaches the previous conservative classification, so no command the previous classifier refused becomes allowed apart from the recorded read-only exemptions.
completion_witness_map:
  - {"condition_sha256":"sha256:639974b33514ee85859a502260dc968e530bef5fce9cbc0b3f050c1f4388cb4c","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:0243c89c86f86a67df4bce2dd6fe927b926389fcc5745dd7723d70278d898a78","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:9c55c43f300180055a6557ae9676c2eb39f679fe53870a8400dbaa873a39ab6b","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:35f9b5e36aa1020b3abec7caf87b3689b4e6b1c88f3c190ad199a48c9f34d759","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:3ba306d2e9a3f68b48c137fe7ce373906631ae8bfaba21f665ff90d7d3942456","witness":"python3 tests/test-hooks.py"}
write_scope:
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/scripts/tool_command_context.py
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
  - Continue from the promoted candidate in the retained task worktree of Plan 104; do not restart the implementation from the committed baseline.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - No shell evaluation, command execution, interpreter-wide allowlist, new runtime protocol or disabled guard.
  - Git repository-selection options and variables, the plan_authoring.py global option grammar and broken-context absolute targets are recorded as separate pre-existing gaps and stay outside this scope.
checked_summary_ja: 実行対象と実行場所を区別しつつ、読み取れない呼び出しは従来どおり止める。

## Decisions

- Answer an invocation the interpreter cannot read as unrecognized, and let the previous patterns decide it. Do not report it as a command that writes nothing.
- Treat an option, an IO number or a command runner in program position as unrecognized, because each means a wrapper or redirection was not modelled here.
- Consume the bounded option grammar of the admitted wrappers and interpreters, including options that take a separate value and the argument terminator.
- Keep the recorded read-only exemptions unchanged: reading a lifecycle file, a documented verification mode and an interpreter program body stay outside write classification.
- Leave Git repository-selection overrides, the plan_authoring.py global option grammar and broken-context absolute targets to a separate plan. They were already allowed before this work and widening scope here would repeat the stop that produced this successor.

## Tasks

- [x] Add a distinct unrecognized answer to the shared interpreter and route it to the previous conservative classification.
- [x] Refuse to read a segment whose program position is an option, an IO number or a program that runs another program named in its arguments.
- [x] Consume the bounded wrapper, interpreter and shell option grammar, including separate option values and the argument terminator.
- [x] Cover every reproduced form and every recorded read-only exemption in the existing hook fixtures.
- [x] Run focused checks, independent review and one authoritative suite for the accepted patch.

## Validation Notes

- Planning baseline: 1c7a310af9c90447c3e868aa8e6dffe7ce0a098e in temp_project.
- Owner instruction: プラン104の実装をエポック1の後継で続行することを承認する
- Plan 104 stopped at parent_remediation_budget_exhausted after one parent-direct remediation round left Medium findings. Its execution ledger could not open a same-plan continuation epoch because a formal review requires Codex reviewer-session runtime evidence that the reviewing session cannot emit.
- The candidate from Plan 104 is promoted into this plan's write scope unchanged. Its focused and authoritative results do not carry over; this plan runs them again for the accepted patch.
- Focused validation on the accepted patch: python3 tests/test-hooks.py reports 89 tests OK, and python3 scripts/check-copier-template.py passes. The root and generated gates are byte-identical after their import line.
- Authoritative validation on the accepted patch, run once: scripts/lint-project-workflow.sh passes (234 tests OK) and REQUIRE_COPIER=1 tests/smoke.sh passes.
- Differential evidence: an 11000-case sweep comparing the previous WRITE_COMMANDS patterns against the accepted interpreter reports no command that the previous classifier refused and this one allows, outside the recorded read-only exemptions.
- Two independent read-only reviews were consumed. Round one raised three High and one Medium finding, round two raised three High and one Medium finding. Each finding was reproduced against the previous classifier and remediated. Round two led to inverting the read-only decision: only a positively validated form may certify a lifecycle file name as data, and a segment that mentions a lifecycle file without a validated form is answered as unread.
- The execution ledger for this plan stopped at descope_pending with parent_remediation_budget_exhausted after the first review was recorded, and the second review receipt is retained outside the repository as a file. The epoch permits no third review, so the remediated state carries no independent review.
- Owner acceptance: 提案の方針で承認する。 The owner authorized accepting the remediated candidate on parent validation and publishing it without a further independent review, with that gap stated.
