# Reject fixture command redefinition

status: checked
primary_invariant: the focused checker rejects a fixture that redefines or shadows any shell command a bound transition observation depends on, so no bound assertion can be made vacuous while its committed text survives
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
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
  - docs/plan/checked/2026/08/16-31/205-integrate-bounded-copier-fixture-validator.md
  - docs/plan/checked/2026/08/16-31/227-complete-bounded-copier-fixture-runtime.md
  - docs/plan/replanned/2026/08/16-31/183-build-bounded-copier-transition-fixture.md
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
  - docs/plan/checked/2026/08/16-31/186-bind-connected-copier-fixture-checker.md
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
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan; Plan 246 owns that file
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 245 must start only after this plan is checked and its exact checked archive path replaces the active dependency
  - do not run tests/copier-update.sh; Plan 179 retains the sole complete transition execution
checked_summary_ja: bound観測が依存するcommandの再定義やshadowingをfocused checkerで拒否する。

## Decisions

- Reject the defect class, not one spelling. A fixture that defines grep, test, touch, sed, kill, wait, or fixture_git as a shell function keeps every bound operation's committed text while the observation it performs becomes vacuous, so the checker must reject the redefinition itself.
- Own the validator and its test together, because widening the prohibition is only acceptable with the mutation coverage that proves it holds.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [x] Reproduce the admission by defining grep, test, and touch as no-op functions in a scratch copy of the committed fixture.
- [x] Reject redefinition or shadowing of every command a bound transition observation depends on, and keep the committed fixture accepted unchanged.
- [x] Add mutation coverage for a function definition, an alias, and a shadowing helper for each protected command.
- [x] Complete fresh independent review and focused validation with zero unresolved High or Medium findings.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pending. The reproduction is recorded in the Plan 187 replanned archive as High finding 1.
- Reproduced the admission: no-op `grep`, `test`, and `touch` declarations appended to a scratch copy of `tests/copier-update.sh` were accepted by the checker before this work.
- A `command_shadowing` rule was implemented in the working tree and passed every declared validation command: `python3 tests/test-copier-fixture-validator.py` (381 tests OK), `python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh`, `python3 scripts/check-copier-template.py`, and `git diff --check`.
- Three independent reviews were run against the working-tree diff. The first returned 2 High and 3 Medium findings, the second returned 4 High and 2 Medium findings after the first parent-direct remediation, and the third returned 2 High and 2 Medium findings after the second parent-direct remediation.
- The remaining findings are that a prefixed search path still reaches an observed command through an unlisted forwarder such as `nice`, that an option word the checker cannot read is dropped rather than reported, and that two search-path binding readings reject fixtures that only mention `PATH` as data.
- Two independently reviewed parent-direct remediation rounds left High and Medium findings, which is the `parent_remediation_budget_exhausted` stop condition, so execution stopped before completion and archival.
- The user then authorized continuing the implementation of this plan directly instead of restructuring it, which reopened the run without changing the primary invariant, the write scope, the validation authority, or any acceptance item.
- The reopened run ran further independent review rounds against the working-tree diff and remediated every High and Medium finding each returned, covering command lookup, search-path binding, path settling, deferred bodies, directory comparison, and the reading of words this checker cannot read.
- Read a word this checker cannot read for the helper paths it spells only when the run is not written as a command this checker models, because a message, a pattern and a script operand carry paths as data while an interpreter carries a program that creates files.
- Read a command written as a path as an unknown command rather than as the utility its last segment names, because a file the fixture puts at `./printf` writes whatever it likes.
- Read a `sed` script as data unless it spells a `w` where `sed` reads one as a command, which is where a script starts, where the option letters before it end, where the name of an option that carries its script ends, after a separator or a quote, with an address before it or none, or where `sed` reads one as the flag of a whole substitution written with any delimiter and after its other flags. Read an address written as a line number, a step, the last line with or without the backslash a quoted word asks for, or a match written between two slashes or between two of any other character a backslash opens, alone or as a range. Read the place rather than the letter, because a `w` anywhere else stands inside a match, a replacement, or a word the script only reads, while a name written straight after the `w` with no blank between is written as readily as one a blank follows. Do not read a blank of its own as a place a command starts at, because `sed` separates commands with a separator or a newline and a blank stands inside a match as readily as between commands. Read past every substitution and transliteration a command stands after, and read the one that stands over it, before reading a write or a text command out of a script, so that a place inside a substitution is read as no command at all, reading the place at the letter the command is spelled with rather than at the character before it, because the character before it is the end of the substitution it follows as readily as a separator of its own, and read the flags of a substitution across the blanks written between them, so a `w` a blank divides from the delimiter that ends a substitution, from the flags before it, or from both is read as writing, whatever delimiter the substitution is written with, while a letter that is no flag at all ends the reading because `sed` runs no such script; read a `w` written that way after a transliteration as writing all the same, because `sed` runs no such script either and a fixture that spells one is rejected rather than trusted, reading a match and a replacement on across a line end a backslash carries, because a delimiter is written with the same characters a script separates commands with, so a substitution whose match opens with one of those letters would otherwise hide the write its own flag spells. Read nothing as a command inside the text an `a`, an `i`, or a `c` carries, because `sed` reads everything after such a command as text it adds to its output rather than as commands, and read that text on to the line after it when a backslash `sed` reads ends the line, counting the backslashes a word written between double quotes carries as half of what is written. Read a run whose text a further word carries as writing, because a text carried across words is not read here. Read the word that spells the write as the path it creates, because a script names the file to write inside its own word rather than as another operand, and read only the text after each write for the helper names it carries, because a path the script matches or puts in its output names no file the run creates.
- Read the list of a `for` head as the paths a write under it may create, because this checker settles no name a loop head binds while the list itself is written in full.
- Record that a script read from a file, such as `sed -f script input`, is outside this reading for the same reason a program text is: the write is written in bytes this checker never reads as a script.
- Read a run given a script that runs a command of its own the way a run given a shell text is read, rather than as a run whose operands are data. `sed` runs a command with `e`, written where a command stands with an address before it or none, and written as the flag of a substitution, glued to the flags before it or divided from them by blanks, and what such a command writes is named nowhere in the script, so the whole of every word is read for the helper names it carries. Read the flag from the substitution it belongs to, because the flags stand inside the run the substitution is read as, and read an `e` a further substitution stands over as data, because a letter inside a match or a replacement runs nothing. The letters an option is written with are read as no place a command stands at here, because the `e` of `-e` is the option rather than the command and a script glued to that option carries the text to run in a word of its own.
- Read the option letters written before a script as blanks of their own length, so a script glued to the option that carries it is read from where the script itself starts. Read those letters up to the first letter an option takes a value after, because a script written after `-e` opens with a letter an option is written with as readily as a command is. Read the name a write spells as reachable when the value it is written with is one this checker cannot place, because a path it cannot place is not a path it has proved lies outside a searched directory.
- Record that a value glued to an option that carries a file name, a backup suffix, or a line length is read as a script here, so a value written to start with a write letter is rejected although `sed` writes nothing. Such a reading rejects rather than admits, and no value a fixture writes for those options is written that way.
- Record one further boundary. A destination read from input or from a command substitution, such as `read -r p` or `p=$(cat f)` followed by `touch "$p"`, names a file no written text fixes, so it is accepted; rejecting it would reject every fixture that writes through a variable.
- Record two boundaries of that reading rather than closing them here. A destination written relative to a working directory set inside a program text, such as `sh -c "cd $tmp/bin && touch grep"`, is outside the reading, because reading it needs the unquoting this checker deliberately refuses. A helper name written inside a program text is rejected wherever it is written, including an unsearched directory, because a refused word is not placed.
