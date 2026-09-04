# Place fixture option words and read alias sources beyond the shell surface

status: in_progress
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
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"The current checker returns zero findings for install \"$topt$tmp/$lane\" AGENTS.md when topt=--target-directory= and lane=update-source, although the resolved option writes into the update source."}
  - {"kind":"bounded_prototype","evidence":"The existing _word_parts and _resolve_parts path resolves that word to a literal --target-directory= prefix followed by the already modelled absolute tmp binding and literal update-source segment."}
  - {"kind":"reproduced_defect","evidence":"The current checker returns zero findings for python3 -c creating $tmp/held as a symlink to $update_source, followed by a copy and Git staging through $tmp/held."}
  - {"kind":"existing_mechanism","evidence":"The existing _is_interpreter, _operation_words, _update_source_names, and _mentions_name helpers identify the bounded interpreter, inline program word, and update-source name without parsing Python or shell program semantics."}
completion_conditions:
  - Target-directory option words composed only of existing bounded assignment values and written literals are resolved before operand classification; attached and following directory values are checked, and non-singleton or unresolvable options fail closed.
  - Existing bounded shell or Python interpreter invocations using an inline-program option are rejected when the written program carries a name that may denote the update-source root, while file or standard-input script invocation remains accepted without parsing program semantics.
completion_witness_map:
  - {"condition_sha256":"sha256:471a8e87f72690454c81a010c8fb6907c8fe3a6d939dafe467b0d1ae24dfc189","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:080059032cf815312934840009af264ff011524c6e3e5fa0719588256b76f214","witness":"python3 tests/test-copier-fixture-validator.py"}
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
- Add a fixture-aware target-directory option reader beside the existing written-option reader. Resolve only words composed from the assignment values and literal segments the current binding model already accepts; do not evaluate parameter operators, command substitutions, arithmetic, splitting, globbing, or shell control flow.
- Accept a resolved option only when every bounded value has one target-directory interpretation. Read an attached directory from the resolved suffix and a separate directory from the following word. Treat no resolution, mixed interpretations, or more than one semantic option value as unplaceable so the existing fail-closed path reports it.
- Preserve ordinary path operands such as `"$root/pyproject.toml"`. Resolution is used to classify a target-directory option only when the settled word starts with an exact supported long-option name or short `-t` cluster; it does not make every expansion-bearing word an option.
- Detect the interpreter case through the existing bounded shell and Python interpreter classifier and the existing inline-program option shape. Reject an inline program word that mentions any name `_update_source_names` says may denote the update source, without deciding what operation the program performs.
- Do not reject interpreter file or standard-input forms. In particular, the committed fixture's `python3 - "$update_source/copier.yml" ...` invocation remains accepted because `-` selects a program from standard input rather than carrying an inline program.
- Do not parse arbitrary interpreter languages. The rule reports the opaque root-bearing inline program as a fail-closed operation; it does not decide whether the program creates a symbolic link, rename, copy, or another alias.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [x] Reproduce both admissions read-only against the checked Plan 248 gate with `tests/copier-update.sh` left byte-identical, and record the finding counts before the change.
- [x] Add the fixture-aware bounded target-directory option reader, resolve only current assignment-model values, and route absent, ambiguous, or mixed interpretations to the existing unplaceable-destination finding.
- [x] Decide the inline `--target-directory=` and concatenated `-t` words by the option and directory values they resolve to, while preserving ordinary expansion-bearing path operands and every rejection checked Plan 248 added.
- [x] Reject a bounded shell or Python inline program that carries an update-source name without parsing the program or deciding which interpreter operation it runs.
- [x] Add mutation coverage for the inline `--target-directory=` form, the concatenated `-t` form, the interpreter-created symbolic link, an ambiguous option value, an ordinary expansion-bearing path, and the committed standard-input Python invocation.
- [x] Complete one fresh independent read-only review and focused validation with zero unresolved High or Medium findings.
- [ ] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Both admissions are recorded as High findings of the tenth independent review of Plan 248 and were reproduced in the main session against that plan's working state with `tests/copier-update.sh` byte-identical.
- Reproduction 1, an option written with its value in one word: with `topt=--target-directory=` in scope, `install "$topt$tmp/$lane" AGENTS.md` and `install "${e}--target-directory=$tmp/$lane" AGENTS.md` produce zero findings, while the same word written with a literal leading dash produces one. The review could not chain this to a silent staging, because the staging rules still report the repository, so it defeats a fail-closed disposition rather than completing an import.
- Reproduction 2, an alias an interpreter creates: `python3 -c "import os; os.symlink('$update_source', '$tmp/held')"` followed by an ordinary copy into `$tmp/held` and `git -C "$tmp/held" add -- AGENTS.md` produces zero findings and imports an undeclared path into the update source. Every word is placeable, so no disposition rule fires.
- Both forms are admitted by the gate committed before Plan 248 as well, so neither is a regression that plan introduced.
- Feasibility was rechecked after Plan 264. The existing binding model resolves `"$topt$tmp/$lane"` to a literal `--target-directory=` prefix plus the already modelled absolute `tmp` value and the literal `update-source` segment. The existing interpreter and update-source-name helpers identify `python3 -c` and the root-bearing program word without interpreting its Python statements.
- This plan must not introduce a parser for an arbitrary interpreter language or a general shell substitution evaluator. An opaque root-bearing operand is a fail-closed finding, not a request to reconstruct its runtime semantics.
- Both admissions are now closed. The option a word reaches its command as is read from the whole leading run of resolved written text, so `install "-$opt$tmp/$lane" AGENTS.md` with `opt=-target-directory=` is reported the same way as the word written with both dashes. Text this checker had to assemble from several resolved parts decides the option only when it names one; every other assembled word is handed back to the reading it already had, so joining the runs never removes a destination that was already read.
- A name every assignment in the fixture writes empty carries the empty string, which the general binding model reports as unreadable because an empty value writes no part. Option classification supplies that value through `_option_bindings`, never the path model, so `install "${e}--target-directory=$tmp/$lane" AGENTS.md` with `e=` is now placed while a path word carrying the same name keeps its fail-closed disposition.
- The empty value is supplied only where the binding model already carries the name and reports it unreadable, and never for a name in `unsettled_for` or `inherited_names`. A reader written above every assignment of the name reads the value this fixture's caller holds, which no written text fixes.
- An equals sign supplies the option value in the same word, so `--target-directory=` with nothing after it names the empty directory and is reported as an unplaceable destination rather than read as taking the next word.
- Differential evidence against the commit this plan started from: 1248 fixtures over option values, word shapes, commands, and operand layouts, and 450 fixtures over option-letter clusters carrying an empty name at three positions. No fixture rejected before is accepted now, and no fixture raises where it did not before. 69 fixtures gain a finding. 36 lose one redundant fail-closed finding while staying rejected, because the word they carry is now read as the option it is.
- Three independent read-only reviews were run. The first found one High defect, an `IndexError` from binding an empty value in the general path model, and two Medium defects, an over-broad short-option cluster reading and a trailing-separator destination that fell into the pre-existing `cp SRC DIR/` hole. The second found one High defect, an empty value supplied to a reader written above every assignment of the name. The third found no High or Medium finding and independently reproduced the differential result over about 15000 fixtures, confirming in a real shell that every recovered acceptance writes nothing into the update source.
- This exceeded the one initial review and one rereview the run-wide review budget allows. The run is therefore stopped for the owner rather than archived. The declared write scope is committed because both authoritative suites pass and the change is measured non-weakening, and this plan stays `in_progress` until the owner accepts or rejects the overrun.
- `tests/root-plan-lifecycle.sh` named this plan's backlog path and asserted `status: backlog`, so activating this plan failed the root agent policy check. That assertion is now resolved from whichever numbered plan predates the admission boundary, which keeps the boundary message it checks and drops the dependency on one unrelated plan's lifecycle location. The file is outside this plan's `write_scope` and is reported as such.
- `cp SRC DIR/` remains silent for a destination written with a trailing separator, including the literal spelling committed before this plan. That hole is pre-existing and independent of the option reading, so it is left for a separate plan rather than widened here.
