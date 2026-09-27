# Let the sandboxed runner execute its Python helpers and Python workers when the runner itself runs from a uv-managed virtual environment

status: checked
primary_invariant: Whatever interpreter runs the sandboxed runner, every Python process it starts inside Bubblewrap receives that interpreter's real runtime read-only and nothing else beyond the existing mounts, so the runner behaves identically from the system Python and from a uv virtual environment.
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
standing_continuation_authorization: 420 プランはすでに実装されているため、 こちらに 4回レビューまで承認を求めなくともよいようにしていたはずだが
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"On 2026-09-26 running the runner suite with the repository .venv Python failed three cases with bwrap: execvp .../.venv/bin/python3: No such file or directory, because .venv/bin/python3 links to ~/.local/share/uv/python/cpython-3.13.2-linux-x86_64-gnu/bin/python3.13 outside every sandbox mount.","kind":"reproduced_defect"}
  - {"evidence":"collect_candidate_patch_in_sandbox runs sys.executable -c <helper> inside build_bwrap_command, so the runner's own candidate patch collection fails whenever sys.executable is a venv link, not only the tests.","kind":"existing_mechanism"}
  - {"evidence":"build_bwrap_command already read-only binds the first ancestor of an absolute command that contains bin and lib at its original path; applied to the resolved interpreter it mounts the uv CPython prefix, while the unresolved venv link mounts only .venv.","kind":"existing_mechanism"}
completion_conditions:
  - Candidate patch collection and every other runner-started Python inside Bubblewrap launch the resolved real interpreter with -I and only its admitted runtime root mounted read-only, including a deterministic case where the runner's interpreter is a link whose target lies outside every existing mount.
  - A custom worker whose executable is a venv interpreter link receives the venv root, identified by its pyvenv.cfg and its link to the base interpreter, and the base installation prefix read-only, so its standard library and packages load, and no writable or other host path is added.
  - Under the system Python the mounts are unchanged and every existing runner case passes; the only argv change is the canonical interpreter path and -I for runner-started helpers.
  - The base root is admitted only as the interpreter's prefix holding its standard library and a venv root only with a pyvenv.cfg naming that base; either is refused before Bubblewrap starts when it equals or contains HOME, CODEX_HOME, the repository, the clone or the scratch, or lies inside the clone or scratch.
  - Both runner copies stay byte-identical, and both orchestration guidance copies and CHANGELOG.md state which interpreter paths the sandbox mounts.
completion_witness_map:
  - {"condition_sha256":"sha256:f7393cf717d333f32d6d79bca8cc7477ddf3d0bd5ba69b59d869819c967542db","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:235e4972520fba02f2b280dff11358b6665134261f63d5559e7fb54a862ef74c","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:b757f9167d4257bdeaea6ec01ec893a82544f684c2110988b03ec7ba6798e1a9","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:98eafe7b74e2e3b4ce94f78ea36bfc2112cd8e6a1f2610dc73d2b6dbc185d6fd","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:6897f07b1e721832c71fb9d1dc759884f462e8fb205fbb0f2ee907a16ff27a71","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/run-sandboxed-plan-worker.py
  - template/.project-agent-workflow/scripts/run-sandboxed-plan-worker.py
  - tests/test-sandboxed-plan-worker.py
  - references/orchestration.md
  - template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md
  - CHANGELOG.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - scripts/AGENTS.md
  - tests/AGENTS.md
  - pyproject.toml
  - uv.lock
  - references/validation.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The sandboxed runner and its tests work unchanged when run through uv run --locked from a task worktree's .venv.
  - The sandbox gains only read-only interpreter runtime mounts and no writable, credential or unrelated host path.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:567a76a155c4a548eebbe22269db022c2d54b54ca21f6bf8687a098dbf5dd6b0","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"acceptance_sha256":"sha256:231ec815ba76a35aede7f5284270984628f6a3cc4c5ed0e3f34ff3f727907713","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
integration_gates:
  - docs/plan/backlog/422-provision-task-worktrees-with-the-locked-uv-environment.md must reach a checked archive before this plan starts, because its task worktree provisioning creates the .venv this plan runs under.
checked_summary_ja: ランナーを uv の仮想環境の Python で動かしても、サンドボックスの中で Python の補助処理とワーカーを実行できるようにする。

## Decisions

- Keep the parent orchestrator's final ownership and implement parent-direct with the parent-owned execution ledger, because this plan changes the sandbox mounts.
- Run in-sandbox runner helpers with os.path.realpath(sys.executable) and -I, so they need only the base interpreter's standard library, and mount that interpreter's installation prefix, identified by its standard-library landmark rather than by a bin-and-lib ancestor, read-only.
- For a custom worker executable that is a venv interpreter link, admit the venv root by its pyvenv.cfg and its link to the base interpreter, admit the base prefix by its standard-library landmark, and mount both read-only at their original paths; mount nothing else and nothing writable.
- Refuse an interpreter runtime root that equals or contains HOME, CODEX_HOME, the repository, the clone or the scratch, or lies inside the clone or scratch, before Bubblewrap starts.
- Keep validation commands resolved through the trusted DEFAULT_PATH unchanged; this plan does not make plan validation use the venv.
- Run this plan's focused runner suite once with the system python3 and once through uv run --locked in the task worktree, and record both results in Validation Notes.

## Tasks

- [x] Before product edits, prepare the parent-direct execution ledger with prepare-parent-direct, record the review-route check, and record the unchanged baseline results of the focused suites.
- [x] Resolve the helper interpreter and the custom worker interpreter and add the read-only runtime mounts in both runner copies.
- [x] Add cases for a venv-link runner, a venv-link custom worker, a system interpreter, an interpreter inside the clone and a runtime without bin and lib, and run the suite under both the system Python and uv run --locked.
- [x] Document the interpreter mounts in both orchestration guidance copies and CHANGELOG.md.
- [x] Record a passing adversarial preflight, obtain independent review through a fresh read-only Codex reviewer whose first prompt carries the ReviewPacket marker, resolve findings within the existing budget, run the focused checks, then the authoritative suites once, and publish through manage-plan-worktrees.py without pushing.

## Validation Notes

- Owner instruction on 2026-09-26 asked to define these environment and workflow changes as rules and to create plans for them: create each task worktree's .venv with uv, let Bubblewrap run the .venv Python, replace the retired gpt-5.3-codex-spark with gpt-5.6-terra medium, fix the check-time plan-id reservations, and approve continuations up to the fourth review once at plan start (option A).
- standing_continuation_authorization quotes the owner's words of 2026-09-27, given in the plan 421 conversation after it asked twice for continuation approval. The owner then chose to record that approval in the plan file (「2 の計画で作成する。」); plan 424 added the field here.
- Parent-direct implementation was prepared against source `1fc0a44f30c326023864d3ce7b20fd490a516896` with `prepare-parent-direct`. `standing-authorization` took the owner's quotation from this plan's `standing_continuation_authorization` line before any review. A runtime-proven read-only route probe was recorded before product edits. No writable helper was used.
- Baseline, run serially: `python3 tests/test-sandboxed-plan-worker.py` passed 268 tests under the system Python and failed 43 with 2 errors through `uv run --locked`, 41 of them with `bwrap: execvp .../.venv/bin/python3: No such file or directory`. `python3 scripts/check-copier-template.py` passed. A first attempt that ran both suites concurrently in one worktree also failed the live-evidence cases under the system Python; those cases pass when run alone, so the concurrent runs shared state and were discarded as baseline.
- Final behavior: candidate patch collection launches `os.path.realpath(sys.executable)` with `-I` and mounts, read-only, only that interpreter's installation prefix, the parent of its `bin` directory holding `lib/pythonX.Y/os.py`, and nothing when the interpreter lies in the system directories. A custom worker whose executable is a venv interpreter link keeps its unresolved path and receives the venv root, admitted only when its `pyvenv.cfg` `home` names the resolved base interpreter's directory, and that base prefix, both read-only. Each root must be canonical and is refused before Bubblewrap starts when it equals or contains `HOME`, `CODEX_HOME`, the repository, the clone or the scratch, or lies inside the clone or scratch. The Codex worker, validation and non-venv custom workers keep the previous mounts, and validation still resolves through `DEFAULT_PATH`.
- Formal review 1, in a fresh read-only Codex session whose first prompt carried the ReviewPacket marker, reported `REVIEW-VERDICT: none` after an exact-target adversarial preflight. No continuation was needed; one of the four cumulative reviews was used.
- Regression proof: all six new cases fail against the source-baseline runner under both interpreters; the real venv custom-worker case fails behaviorally because the baseline resolves the venv link and loses the venv package. Throwaway adversarial cases passed 10 of 10 under both interpreters, including a symlink chain through the venv, a non-canonical venv alias, an oversized or versionless `pyvenv.cfg`, a standard-library landmark escaping its prefix, a read-only venv root and a hidden sibling path inside real Bubblewrap, and a HOME-containing prefix refused before Bubblewrap.
- Focused validation passed: `python3 tests/test-sandboxed-plan-worker.py` ran 274 tests once through `uv run --locked` and once with the system `python3`, and `python3 scripts/check-copier-template.py` passed, which also proves both runner copies byte-identical. Authoritative `scripts/lint-project-workflow.sh` and `tests/smoke.sh` each ran once through `uv run --locked` after the clearing review and passed. The completion and archive execution gates passed before the implementation commit.
- Accepted implementation commit: `6f63ee3`. The external ledger, standing authorization, receipts, review evidence and validation output are retained under `~/.local/state/project-agent-workflow/plan-423-20260927/`. Link changes: none.
