# Place fixture option words and read alias sources beyond the shell surface

status: backlog
primary_invariant: the focused checker names the option a written word reaches its command as, and fail-closes an operation that gives the update-source root a second name or carries that root through an opaque inline interpreter program without interpreting arbitrary interpreter semantics
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: ordinary
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
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/244-reject-fixture-command-redefinition.md
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
  - tests/copier-update.sh
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
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 248 must be checked before this plan starts, because it owns the option reading and the alias rule this plan widens
checked_summary_ja: option語の判定を語のテキストから値の配置へ移し、interpreterが作る別名も報告できるようにする。

## Decisions

- Place the name a word carries instead of guessing from its text. Checked Plan 248 decided whether a word may reach its command as an option by reading the word itself, and three review rounds in a row defeated that reading by moving one expansion in front of the dash. The text of `"$topt$tmp/$lane"` and the text of `"$root/pyproject.toml"` are the same shape, so no predicate over the written characters separates them.
- Resolve the update-source root only through an already bounded shell expansion form. Do not add a general shell substitution evaluator; an opaque root occurrence in a path, option value, aliasing operand, or inline program is rejected rather than treated as harmless.
- Report an alias of the update source without gating on the command name. Checked Plan 248 closed `ln` and `mv` by name, which an interpreter running an inline program never matches. A name list keeps losing to the next spelling, so the rule reads a root-bearing operation instead of relying on its command name.
- Do not parse arbitrary interpreter languages. Reject an inline program that carries the update-source root without deciding whether the program creates an alias.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [ ] Reproduce both admissions read-only against the checked Plan 248 gate with `tests/copier-update.sh` left byte-identical, and record the finding counts before the change.
- [ ] Resolve only the exact bounded nested expansion form needed to place the update-source root, and reject opaque root-bearing operands without a general shell evaluator.
- [ ] Decide an option word by the name its expansions settle to rather than by its written characters, and keep every rejection checked Plan 248 added.
- [ ] Report an operation that names the update-source root in an aliasing position or opaque inline interpreter program without deciding which interpreter operation the program runs.
- [ ] Add mutation coverage for the inline `--target-directory=` form, the concatenated `-t` form, and the interpreter-created symbolic link.
- [ ] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. Both admissions are recorded as High findings of the tenth independent review of Plan 248 and were reproduced in the main session against that plan's working state with `tests/copier-update.sh` byte-identical.
- Reproduction 1, an option written with its value in one word: with `topt=--target-directory=` in scope, `install "$topt$tmp/$lane" AGENTS.md` and `install "${e}--target-directory=$tmp/$lane" AGENTS.md` produce zero findings, while the same word written with a literal leading dash produces one. The review could not chain this to a silent staging, because the staging rules still report the repository, so it defeats a fail-closed disposition rather than completing an import.
- Reproduction 2, an alias an interpreter creates: `python3 -c "import os; os.symlink('$update_source', '$tmp/held')"` followed by an ordinary copy into `$tmp/held` and `git -C "$tmp/held" add -- AGENTS.md` produces zero findings and imports an undeclared path into the update source. Every word is placeable, so no disposition rule fires.
- Both forms are admitted by the gate committed before Plan 248 as well, so neither is a regression that plan introduced.
- This plan must not introduce a parser for an arbitrary interpreter language or a general shell substitution evaluator. An opaque root-bearing operand is a fail-closed finding, not a request to reconstruct its runtime semantics.
