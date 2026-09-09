# Record the verification gate each downstream project actually has, and stop requiring a command the isolated clone cannot run

status: checked
primary_invariant: The downstream baseline record states only commands the isolated clone can actually run, and a project whose own gate needs installed dependencies is recorded without one instead of carrying an invented command.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The runner refuses a baseline that declares no validation command, so every project had to declare one. Running it against the real baselines printed npm error Missing script: typecheck for curiretas-gakumas-portal, because that project has no such script and the command was invented to satisfy the requirement.","kind":"reproduced_defect"}
  - {"evidence":"Each of the three projects declares npm run verify as its gate, and every one of those definitions runs a build or a type generator that needs installed dependencies. The runner verifies a fresh git clone, which carries none, so no recorded npm gate can run there.","kind":"reproduced_defect"}
  - {"evidence":"The verification helper already runs the generated change-aware validation inside the updated clone and already reports change_validation_failed with the template as owner, so the template obligation stays checked for a project that records no gate of its own.","kind":"existing_mechanism"}
completion_conditions:
  - A baseline that declares no validation command is accepted and verified, while a declared command that is not a non-empty list of non-empty strings is still refused with its named reason.
  - The committed baseline record declares no command that the project does not have and no command that a fresh clone without installed dependencies cannot run.
completion_witness_map:
  - {"condition_sha256":"sha256:ccc5c760fd2031c20fd81a11fee477c7ce8458e8c8d317570181b89258eeff65","witness":"python3 tests/test-verify-copier-update.py"}
  - {"condition_sha256":"sha256:62408d33d91f41d42935280231b0f2fdfb020c4d8645ea222ac8d376870edc75","witness":"python3 tests/test-verify-copier-update.py"}
write_scope:
  - scripts/verify-downstream-baselines.py
  - docs/downstream-baselines.yaml
  - tests/test-verify-copier-update.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - .codex/skills/verify-copier-update/scripts/verify-copier-update.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-verify-copier-update.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Every command in the committed downstream baseline record exists in the project it names and can run in the isolated clone, and a project with no such command is recorded without one.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:dbcbc9f905ff9de2eee153a72f6af47f1728bc53c09bb46b1670ac4016daab3c","stage":"focused","witness":"python3 tests/test-verify-copier-update.py"}
checked_summary_ja: 下流プロジェクトが実際に持つ検証手段を記録し、隔離した複製では走らない命令を必須とするのをやめる

## Decisions

- Make the validation command list optional rather than replacing the invented commands with real ones, because every real gate these projects declare needs installed dependencies that a fresh clone does not carry, so a truthful record cannot always name a command.
- Keep the template obligation covered by the generated change-aware validation that already runs inside the updated clone, rather than installing project dependencies during verification, because installing them would reach the network and describe whatever the registry holds instead of the update under test.
- Keep refusing a declared command that is not a non-empty list of non-empty strings, so making the field optional widens what may be absent without widening what may be written.

## Tasks

- [x] Make the validation command list optional in the runner while keeping every existing refusal for a declared command.
- [x] Replace the invented commands in the committed baseline record with the truth for each project.
- [x] Cover the absent and the unusable command shapes in the skill tests.

## Validation Notes

`python3 tests/test-verify-copier-update.py` を実行し74件成功した。記録された検証命令が素の複製で走らない起動子を使っていないことを確かめる検査と、検証命令を持たない記録が受理される検査を新しく含む。

`scripts/lint-project-workflow.sh` を実行し通過した。`tests/smoke.sh` は commit 後に実行する。複製元が commit 済みの内容のみを見るためである。

本計画は Tier 1 のため独立レビューを求めていない。記録の誤りは実行して初めて判明した。`npm run typecheck` は curiretas-gakumas-portal に存在せず、supportcard-status には無関係な `python3 -m compileall` を書いていた。いずれも「検証命令を1つ以上宣言せよ」という要件を満たすために作られたものである。
