# Repair the release runbook's unexecutable steps

status: checked
primary_invariant: The runbook's documented commands and phase boundary match the repository's actual tooling and policy, and the repair changes no authorization rule and grants no new external-effect authority.
task_types:
  - skill_authoring
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The runbook's downstream-baseline command passes --source-commit and --output, and running it exits 2 because scripts/verify-downstream-baselines.py defines --source-ref and --output-dir.","kind":"reproduced_defect"}
  - {"evidence":"tests/validation_tools/release_skill.py already reads this runbook and runs its Git examples through the existing aggregate entrypoint, so the repair needs no new validation gate.","kind":"existing_mechanism"}
completion_conditions:
  - Every command the runbook tells an agent to run names options the corresponding script accepts.
  - The preparation phase ends after the local task publication the repository requires of every task, and no remote effect falls inside it.
  - The publication sequence contains an executable step for each effect it later reports, including the tag push and the Release publication.
completion_witness_map:
  - {"condition_sha256":"sha256:d4f7e8bc53ec4dee6ecdc565a6d9834d26422dc5ae858c89dfdbfcbbb29c3f22","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:af626828601a6e2dc357b33f49a3da25fe6e18945b7deee0b240a842834adb52","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:871235150ae8c432eb378447e6e6115a1e6dbb8bf78ee7890a092b20f0b52dd9","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - .codex/skills/release-project/references/workflow.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - .codex/skills/release-project/SKILL.md
  - scripts/verify-downstream-baselines.py
  - scripts/manage-plan-worktrees.py
  - tests/validation_tools/release_skill.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - python3 scripts/validate-changes.py --all
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - An agent can follow the release runbook end to end without improvising a command, crossing the preparation boundary, or inferring a missing publication step, under unchanged authorization rules.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:52b4706c45072e3ef895ade7370e0d1da6b05241ccb5c3f830a9c09c7b11b87d","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
checked_summary_ja: リリースランブックの実行できない手順を修理する。

## Decisions

- Repair the runbook body only. The skill's authority model, the parity exemption, the regressions, and every generated artifact stay unchanged.
- Document the tag push and the Release publication as steps that consume the authorization obtained earlier, rather than as new authority. The runbook already required a separate exact authorization for each effect.
- Read the peeled ref when comparing an existing remote annotated tag, because the plain ref names the tag object and not the commit it dereferences to.
- Keep the preparation boundary after the local task publication, because that operation is local, is required of every repository-changing task, and performs no remote effect.

## Tasks

- [x] Correct the downstream-baseline command to the options the script accepts, and confirm the corrected form reaches the script's own logic instead of failing argument parsing.
- [x] Move the preparation boundary after the local task publication step, and state in that step that it is local and needs no external authorization.
- [x] Add the tag push and the published-tag confirmation to the tag step, and add the Release publication to the post-tag step, each bound to the authorization obtained earlier.
- [x] Compare an existing remote annotated tag through its peeled ref, and say which line is the tag object and which is the commit.
- [x] Extend interrupted-release recovery to read the task worktree, its temporary branch, any journaled local publication, and the plan's own lifecycle state, not only remote refs.
- [x] State the stop, preserve, and report behaviour for a failed live downstream update, and forbid forcing it or hand-editing generated files.
- [x] Align the unavailable-check wording with the skill's rule that an incomplete suite stops publication.
- [x] Require the release plan to name the chosen version, and say that the version check compares the change log and README rather than the plan.
- [x] Run the focused witness and then the authoritative suite once.

## Validation Notes

## Validation Notes

- `python3 tests/test-validation-tools.py` passes with 316 tests. `python3 scripts/validate-changes.py --all`, `scripts/lint-project-workflow.sh`, and `tests/smoke.sh` each exit 0.
- The corrected downstream-baseline command was run directly: with `--source-ref` and `--output-dir` it reaches the script's own baseline logic instead of failing argument parsing, which is what the previous form did.
- Both documented `inspect` invocations were run directly and reached the command's own logic, so the plan-path form and the direct-task form are each complete as written.
- Two independent read-only review rounds ran against this repair. The first confirmed all eight original findings addressed except interrupted recovery, and reported three defects the repair itself introduced: the source branch was never pushed before the pull request, the authorization step preceded the concrete tag and Release payloads, and the recovery command was invalid and overclaimed its output.
- One parent-direct remediation round fixed all three. The second review round confirmed both high-severity items resolved and the step-number cross-references still accurate, leaving one residual item: the direct-task recovery form omitted its executable prefix. That was a missing command prefix rather than a design question, so it was completed with the reviewer's own corrected text and verified by running the command, and no further design change was made.
- The repair changes documentation only. It grants no new external-effect authority: every effect still passes the per-effect authorization in step 7, which now states explicitly that it does not pre-approve a payload that does not yet exist.
