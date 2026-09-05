# Run one bounded parent-owned preflight per candidate

status: backlog
primary_invariant: A parent may obtain bounded diagnostic feedback from an admitted candidate in a fresh credential-free network-isolated clone without granting worker validation authority or consuming, replacing, or resetting acceptance and correction gates.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: C
human_design_required: yes
human_approval_status: pending
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"existing_mechanism","evidence":"run-sandboxed-plan-worker.py execute_validation_operation already applies an admitted patch in a fresh clone and executes with include_codex_home=False and network_enabled=False."}
  - {"kind":"existing_mechanism","evidence":"Code inspection shows validate_candidate records focused_failed after a failed focused suite, while correct_worker accepts only admitted or focused_passed; reusing focused validation is therefore not a pre-review feedback loop."}
  - {"kind":"existing_mechanism","evidence":"verify_candidate_manifest and the existing one-correction receipt and lineage checks provide candidate identity and bounded retry primitives; no live-worker communication service is needed."}
completion_conditions:
  - The new parent-only preflight verifies the admitted candidate and parent diff/invariant approval, executes one exact predeclared focused command without shell expansion, and rejects unlisted commands and stopped or mismatched attempts before process start.
  - Preflight uses a fresh clone without credentials or network and leaves source, admitted patch, receipt, validation authority, and authoritative/focused counters unchanged.
  - At most one preflight per candidate is admitted atomically; timeout and output limits terminate execution and bound the report, while duplicate, concurrent, stale, and replayed requests cannot start another process.
  - Preflight failure may inform only the existing one correction; the next candidate still needs independent review, focused validation, and authoritative validation, and an exhausted or diagnosis-required run remains stopped.
  - The existing execution ledger tests retain every stopped-state and review-budget guarantee.
  - Root and generated runner and orchestration policy remain aligned after adding the diagnostic operation.
completion_witness_map:
  - {"condition_sha256":"sha256:e5d65c853ce545cc8742c03c742f0d5effd5134ef499d8bf01ad81d4201dc601","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:ea30575c95a9f2d5ae88b3ab49f260dd8f9e2a46b0504394ff0e46a3984d6b31","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:6e7d56c85f748f189e1c8b1bc19218f48496690406216c0c773253d069d21676","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:558a3782f525622fc3d56bc995796656000ccc94d420049f54901a21e30d2f13","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:728e0f35dc7c1436aa68022bcd06238b1b5a33168d7b9dad0370cfe9a53c3c80","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:bae5e525455af13ed900e9d52e0fed042ae4ca94c2dc16de2264cb1195a66c3e","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - scripts/check-copier-template.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/plan-execution-state.py
  - scripts/plan_validation_commands.py
  - tests/test-plan-execution-state.py
  - docs/plan/checked/2026/09/01-15/268-restore-large-test-baseline-and-ci.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
  - python3 scripts/plan_validation_commands.py --self-test
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Implement a parent-only diagnostic operation with immutable candidate binding, isolated execution, one-start claim, timeout and output bounds, and no worker or external-effect authority expansion.
  - Use diagnostic failure only as evidence for the one existing correction and never as formal validation, a review-budget reset, a stopped-run escape, or an acceptance witness.
  - Preserve the execution ledger, diagnosis-required stop, and correction and review budgets.
  - Preserve root/generated policy and runner alignment when adding the parent-only diagnostic operation.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:d64e98c52600eed13d7fcff47b9628c64dba5aa0c9b067b208dbc29e679df7bf","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:c131e4c44de7c19ab8532056cef37ff49aa4c0ea8c42e2be57003bc59b8ae552","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:eab4ede50796930c3e5489f5961522665ce7d575d7d41f08863aed230dfabc10","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:2ebef90d4dc46d64aaef4aa07ba36edca4a69bf13f4ef7ff83e97fe698723f44","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Obtain explicit owner approval of this class C design before promotion or implementation; creating this backlog plan does not supply that approval.
  - Start only after plan 268 is checked and plan 275 has finished its policy relocation; use the resulting green baseline and canonical policy destinations.
  - This is high implementation risk; do not dispatch it to Spark, Terra, or the writable sequential-plan worker. Use one bounded parent implementation with independent review and the existing external execution ledger.
  - Select exactly one command already declared in focused_validation by index; introduce no plan field, free-form shell command, live-worker IPC, remote service, or validation-definition editing permission.
  - Before execution, the parent reviews the admitted diff and critical invariant and supplies the existing explicit approvals; independent staged review follows preflight, not precedes the parent safety review.
  - Default limit is 60 seconds with a maximum of 120 seconds, and captured stdout plus stderr is capped at 64 KiB; timeout or output overflow kills the process group and cannot trigger an automatic retry.
  - Bind a mode-0600 parent-owned claim outside the repository to the verified attempt id, candidate-manifest digest, patch digest, command digest, and execution genesis; claim atomically before launch and fail closed on incomplete crash evidence.
  - Permit no second preflight for the same candidate, even after process failure; a correction candidate has its own identity but remains under the same run-wide single-correction budget.
  - Record preflight output only in a separate bounded diagnostic artifact, never in completion_witness_map or validation_witness_map and never as focused or authoritative success.
  - Before correct can start, the parent must close the matching open attempt through the existing correction_requested outcome with the candidate digest, primary invariant digest, and diagnostic evidence digest; use only an already allowed implementation reason code and never reclassify authority drift as a test failure.
  - Recheck existing ledger stop gates at operation start and before offering correction. Do not add a diagnostic-preflight ledger event or change ledger or candidate-manifest schemas; the existing mandatory `adversarial_preflight` event remains a separate exact-target review-order gate and cannot be satisfied by this diagnostic artifact alone.
  - Hold the existing plan_execution_lease, using its established lock order, continuously from the final stop/baseline recheck through candidate binding, atomic claim, and subprocess start; never release it between a successful check and spawn.
  - Add stop-versus-start race tests proving that an already committed stop prevents claim and spawn, and that no stop event can interleave in the protected check-to-spawn interval.
  - Keep original worker credentials inaccessible to tested code and retain read-only dependencies plus scratch-only caches; abort if existing isolation prerequisites are missing.
  - After the single correction has been used, later findings must stop through the existing policy rather than opening another retry.
checked_summary_ja: 候補生成後に親だけが隔離環境で短いテストを実行し、正式検証と権限境界を変えずに既存の一回の訂正へ結果を渡せるようにする。

## Decisions

- 対象は、候補生成後かつ正式レビュー前に親が隔離複製で実行する短いテストである。
- 本プランのフィードバックは、worker の実行中ではなく、候補生成後から正式レビュー前までを対象にする。
- worker が任意のテストを自分で実行する仕組みや、実行中の worker と通信する常駐処理は追加しない。
- 親が変更差分と重要な不変条件を確認した候補だけを、資格情報とネットワークを持たない複製で実行する。
- 対象コマンドは、そのプランが既に宣言している focused_validation の一件に限定する。
- この実行結果は診断情報であり、正式検証の成功、承認、完了証拠にはしない。
- この隔離実行は、正式レビュー前に必須となる exact-target adversarial preflight の証拠生成を補助できるが、単独ではその台帳イベントを記録せず、対象・仕様・case evidence の照合を代替しない。
- 失敗結果を親が訂正指示へ渡す場合も、既存の候補生成一回と訂正一回の上限を共有する。
- 停止済みの実行、レビュー予算の枯渇、正式検証失敗後の診断要求を、この操作で解除しない。

## Tasks

- [ ] Add failing lifecycle and isolation fixtures showing the difference between advisory preflight and a formally failed focused suite.
- [ ] Implement a parent-only preflight subcommand reusing verified candidate loading, exact command parsing, fresh-clone setup, and credential-free Bubblewrap execution.
- [ ] Implement one-start claim persistence and bounded subprocess streaming/termination; do not buffer unbounded output before applying the limit.
- [ ] Add a diagnostic-only result record with exact command, candidate and attempt digests, exit/timeout/output-limit status, bounded output, and elapsed time; omit secret-bearing host paths and environment values.
- [ ] Test success, failed test, timeout, output flood, descendants, duplicate/concurrent calls, changed candidate, crash/replay, missing isolation, and every existing stopped-run gate.
- [ ] Test an initial preflight failure followed by the one eligible correction and its preflight; prove that all formal acceptance gates remain required and another correction is refused.
- [ ] Update aligned orchestration policy with the parent safety review, diagnostic feedback, formal review, focused validation, and authoritative validation order.
- [ ] Run focused validation, obtain independent review within the unchanged run budget, and run authoritative validation once.

## Validation Notes

- Planning baseline: `987ed43` in `temp_project`.
- Owner request: 「指摘事項についてそれぞれプランを作成せよ。」
- This request authorizes preparing the backlog scope; it does not activate this plan, authorize product implementation now, or continue an unrelated stopped run.
- Feasibility evidence above is source inspection, not a claim that the proposed implementation or its future tests have passed.
- At activation, resolve every dependency to its unique checked record, confirm that the current source still supports this scope, and record the baseline before implementation.
- The parent owns policy interpretation, write-scope admission, review acceptance, validation, lifecycle changes, and commits; helpers have no write authority.
- No measured resource saving is claimed; completion of this plan requires its declared correctness witnesses, not an assumed productivity gain.
