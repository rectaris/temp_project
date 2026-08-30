# Bind fixture inputs to one inventory

status: checked
primary_invariant: the focused checker rejects any copy into or Git staging against the fixture update source that the single Copier update inventory loop does not perform, so the fixture cannot take an undeclared source input
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
preservation_scope:
  - none
context_files:
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/plan/checked/2026/08/16-31/182-admit-v145-copier-wiring.md
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
  - tests/copier-update.sh
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
required_specs:
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
validation:
  - python3 tests/test-copier-fixture-validator.py
  - python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh
  - python3 scripts/check-copier-template.py
  - git diff --check
acceptance:
  - Require every acceptance item to identify its earliest parent-owned static, focused, or authoritative validation witness; reject a new integration lane that reaches its first executable witness only in the authoritative suite when a narrower safe preflight is available, and keep Copier fixture copy and Git staging inputs derived from one inventory.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
successor_plans:
  - docs/plan/active/244-reject-fixture-command-redefinition.md
  - docs/plan/active/245-bind-fixture-inputs-to-one-inventory.md
  - docs/plan/active/246-bind-pre-schema-fixture-contents.md
  - docs/plan/active/247-verify-plan187-successor-acceptance.md
inherited_acceptance_digests:
  - sha256:251de7e9d22d4d2657f9b3890114005a890bceab1a44b54dda2f63cf690d96d1
replan_sources:
  - docs/plan/active/187-verify-plan183-successor-acceptance.md
replan_contract: docs/plan/replanned/contracts/187-verify-plan183-successor-acceptance.json
integration_gates:
  - Plan 244 must be checked and its exact checked archive path must replace the active dependency before implementation
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan; Plan 246 owns that file
  - do not change tests/fixtures/orchestration/copier-update-source-inventory.txt in this plan
  - Plan 246 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: 単一inventory以外からのcopyとGit stagingをfocused checkerで拒否する。

## Decisions

- The existing rule only rejects an outside operation that references the loop variable, so a hard-coded destination path escapes it. Bind the prohibition to the update source destination instead of to the variable spelling.
- Keep the inventory file itself unchanged. This plan constrains how the fixture may consume the inventory, not what the inventory declares.
- Use bounded parent implementation because this is a validation-authority path.

## Tasks

- [x] Reproduce the admission by adding a hard-coded copy into the update source and a matching staging call after the inventory loop in a scratch copy.
- [x] Reject every copy into and staging against the update source that the unique inventory loop does not perform, regardless of how the destination is written.
- [x] Add mutation coverage for a hard-coded path, an indirect variable, and a staged path that no inventory line declares.
- [x] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded in the Plan 187 replanned archive as High finding 2.
- The admission recorded in the Plan 187 replanned archive as High finding 2 is
  reproduced and closed. The checker now settles the update source from the
  destination the unique inventory copy writes, so a hard-coded path, a further
  variable bound to that directory, and a path written through a command
  substitution are all read as the same directory.
- A write into the update source outside the inventory region is rejected
  whether it is written as a copy, an installation, a link, a redirection, a
  write this checker cannot place, a command that puts files in place such as
  `tar` or `rsync`, a Git subcommand that writes a tree such as `apply` or
  `checkout`, or a directory change into the update source that would make the
  following writes relative.
- A staging against the update source is rejected when it is written as `add`
  or `stage`, when it stages everything the tree holds, when it names a path
  this checker cannot place, and when nothing else in the fixture writes that
  path into the update source. A staging this checker cannot read as a direct
  Git run, such as one launched through `xargs` or written inside `sh -c`, is
  reported rather than skipped.
- The committed fixture stays accepted: it edits a copied file in place with
  `sed -i` or an interpreter and stages exactly that path at three sites, it
  stages other repositories freely, and it changes directory 39 times without
  entering the update source.
- Focused validation: `python3 tests/test-copier-fixture-validator.py` (438
  tests), `python3 scripts/project_workflow/copier_fixture_validator.py --check
  tests/copier-update.sh`, `python3 scripts/check-copier-template.py`, and
  `git diff --check` all pass. Eight targeted mutants of the new logic are all
  killed, and 22 spliced attack cases are rejected while the committed fixture
  and four legitimate shapes stay accepted.
- Boundary: a write performed inside an interpreter heredoc is not modelled,
  and an interpreter must keep licensing a staging, because the committed
  fixture edits `copier.yml` in the update source that way before staging it.
  Separating that from a new file created the same way requires reading the
  inventory contents, which this plan's integration gates place outside its
  scope.
- One read-only advisory review agent was used. Its findings were reproduced
  and fixed in this session, and acceptance stayed in the main session.
- A second review round closed two further evasions. An update source carried
  under another name is now followed through a `for` word list and through a
  positional parameter one call site writes the update source into, and
  `update-index` is read as a staging while `hash-object` is read as a command
  that puts files in place. A directory change written inside a command
  substitution is exempt, because it ends with the substitution.
- Boundary: a name that receives the update source through a file rather than
  through a binding, such as one read back with `$(cat …)`, is not followed.
  Recovering it needs a value model this text-only checker does not hold.
- Focused validation after the second round: 441 tests pass, the committed
  fixture is still accepted, 11 targeted mutants of the new logic are killed,
  and `scripts/lint-project-workflow.sh` and `tests/smoke.sh` both pass.
