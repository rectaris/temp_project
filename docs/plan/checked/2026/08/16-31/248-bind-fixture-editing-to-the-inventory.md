# Bind fixture editing acceptance to the inventory

status: checked
primary_invariant: for an operation this checker can read as a shell command whose written words it can name, the focused checker accepts an edit or a Git staging outside the inventory region only when the inventory itself declares the path, and it places a path the fixture reaches through the parameters a call site writes, so neither an editing command nor a helper function can buy acceptance for a path no inventory line carries
task_types:
  - template_workflow
  - security
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: high
implementation_ambiguity: low
implementation_tier: 2
write_scope:
  - scripts/project_workflow/copier_fixture_validator.py
  - tests/test-copier-fixture-validator.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
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
  - docs/plan/checked/2026/08/16-31/246-bind-pre-schema-fixture-contents.md
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
  - docs/plan/checked/2026/08/16-31/245-bind-fixture-inputs-to-one-inventory.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - do not edit scripts/check-copier-template.py in this plan
  - keep the committed fixture passing --check and keep every existing rejection test passing
  - Plan 247 must not resume until this plan is checked
successor_plans:
  - docs/plan/backlog/251-place-fixture-words-and-alias-sources.md
checked_summary_ja: inventoryが宣言しないpathをeditingで通す抜け道を塞ぎ、staging受理をinventory記載pathに束縛する。

## Decisions

- Repair the acceptance side rather than widen the rejection side. Checked Plan 245 already reports a staging that nothing writes; the defect is that any reachable editing command naming a path under the update-source roots buys acceptance without the inventory being consulted.
- Compare against the inventory the fixture reads, because the acceptance clause binds copy and staging inputs to one inventory rather than to the set of paths some command happens to touch.
- Supply the declared paths to the checker instead of recovering them from the fixture text. The fixture builds its inventory path from its first positional parameter, which no supplied byte places, so the checker reads the inventory it ships beside and a caller that knows the inventory passes it directly. An inventory the checker cannot read declares nothing, so every staging outside the region is then rejected.
- Declare `template/.project-agent-workflow/README.md` in the inventory. The update source is a full clone of this repository, so the committed fixture edits and stages that file at the v1.2.3 boundary without any inventory line carrying it. Binding acceptance to the inventory therefore requires the inventory to declare every path the fixture stages outside the region. The added line copies the working tree version of a file the clone already carries, so the fixture builds the same boundary from the same bytes in a clean tree.
- Keep the existing rejection of a staging nothing writes ahead of the new check, so an undeclared path that no editing command names keeps its current message.
- Bind the edit itself to the inventory, not only the staging. The first independent review showed that a fixture can edit an undeclared path and then let `git commit -a` or `git commit -- <path>` carry it, never touching a staging subcommand. Rejecting the undeclared edit closes that route at the source and needs no option-by-option reading of `git commit`.
- Read a staging written inside the body of a called function. The fixture drops an operation the graph reaches through a call, because a Git wrapper body carries `"$@"` rather than the words. A body that writes the subcommand itself does carry them, so the staging read falls back to those words; otherwise one helper function that names the staging hides it from every rule. The fallback is confined to the staging read, so no other rule changes.
- Place a path the fixture reaches through a positional parameter. The second review round showed that a helper bound from `$1` hid the update source from every rule in the region check, not only from the new ones, so the acceptance carve-out could be reopened by one call. The owner approved widening this plan to close it rather than deferring it. A positional parameter is read as a name, a call site binds it to the words it writes, the parameters a body shifts are followed, and a name a body binds from a parameter settles for the readers written below it inside that body. Every reachable call site is read together, which names more values than one run holds and never fewer.
- Read a substitution against the assignment that writes it rather than against the value it resolves to. A body assignment that only reads an outer name inherits a value the outer binding already proved runs once, so keeping it unproven blocked the parameter chain without proving anything.
- Accept that two older tests now record a stronger result. A write bound from a parameter is reported as reaching the update source instead of as a write this checker cannot place, and a Copier copy whose destination one call site names is reported instead of accepted. Both move from accepting to rejecting, so neither weakens the gate.
- Union what every call site and every possible shift distance can bind instead of returning nothing when the binding is uncertain. Returning nothing reproduced the same fail-open the plan repairs, because an unbound name is an unplaceable name. One unreadable sibling call site therefore no longer discards the readable ones, and a name a body binds through a call is resolved recursively under a cycle guard.
- Count a shift as certain only when it runs unconditionally at the script level and lies inside no nested conditional, detached, or loop extent within its declaration. A shift a loop carries contributes no bounded distance at all; the parameter list is then read from the smallest reachable index to its end, because any numeric cap on a loop-carried shift would be an assumption the fixture text does not support.
- Report a path operand this checker cannot place instead of treating it as harmless. Every review round found the same shape: make the destination word unplaceable and every rule skips it. Inverting the disposition removes the shape itself rather than one more instance of it.
- Close the unplaceable-path class by placing more words first and reporting only the residue. Loop variables bind to their head words, and a name stays settled across a call unless that call transitively assigns it. Removing the guard alone produced five false positives; each one was a place the model gave up too early, so the guard was replaced by a better model rather than by a looser rule.
- Bind a loop variable to `None` when its head runs a substitution once per round, mirroring the rule an assignment already follows. Binding an opaque segment instead would have weakened the checker, because a non-empty opaque segment stops the write read from reporting the word at all.
- Read which operand a command writes rather than treating every non-option word as a path. A copy-style command writes only its last operand, an interpreter hands its operands to the script it runs rather than editing them, and an expression-taking command carries words that are not paths. Without this the inverted disposition rejected a `sed` expression and a commit message.
- Leave the update-source root name unplaceable and rely on the operand model. That name is assigned from a nested command substitution this checker does not close, but it never stands as an edited or staged path operand in the fixture, so placing it is not required to hold the invariant.
- Keep each command's option table keyed to the command that takes it. A shared table let `sed -r` consume the destination that followed it, and let `rsync -t` be read as a target directory it never names. The same round found a second table shadowing the copy commands the inventory region already rejected, which silently removed a rejection the committed gate held.
- Read a call this checker dispatches from a name it cannot place as assigning every name, so a callee reached through `$runner` can no longer replace a name a reader below it believes settled.
- Classify an option after normalising the quoting of its name half, not on the raw word. `"-t"`, `'-t'`, `-"t"` and `\-t` all reach the command as the same option, and reading them as operands dropped the real destination. Only the name half is normalised, because the value half legitimately carries an expansion.
- Report a staging that names no repository outside the directory it stands in, instead of reporting a `cd` this checker cannot place. The literal form of that finding produced nine false positives on the committed fixture; closing it at the staging keeps the fixture accepted and still rejects a staging whose repository is invisible.
- Treat a word one expansion away from a dash as an option this checker cannot name. `"-t$e"`, `"${e}-t"` and `"$opt"` all reach the command as the same option, so the last operand is no longer proven to be the destination and every operand is read instead.
- Read a word that carries a written path separator as a path even when it carries an expansion. This fixture writes ordinary copy sources as `"$root/pyproject.toml"`, and treating every expansion as unreadable reported them for a source this checker cannot place. A word with an expansion and no written separator stays unproven.
- Read every operand of a renaming or linking command, and report an operand of one that names the update source. Those commands hand the identity of their source to their destination, so reading only the destination let one link give the update source a second name that took every rule below it out of play at once. The root itself names the update source, not only the paths under it.
- Bound the primary invariant to the operations this checker can read as shell commands whose written words it can name. As first written the invariant quantified over every reachable operation, which includes an inline interpreter program, and no static shell reader can decide that. The owner authorized narrowing it after the tenth review round, which is the round that produced the undecidable case. The narrowing changes no acceptance item and no accepted safety condition; it states the surface the gate actually covers instead of implying one it cannot reach.
- Defer the two residual holes to `docs/plan/backlog/251-place-fixture-words-and-alias-sources.md` rather than close them here. Both need a capability this plan does not own: placing the update-source root name through a nested command substitution, and deciding what an inline interpreter program may name. Both are admitted by the gate committed before this plan, so deferring them keeps a strict improvement rather than accepting a regression.
- Stop the review loop at ten rounds. The acceptance item was met and every remaining finding was a new evasion spelling rather than an unmet requirement, so continuing was an unbounded adversarial search against an invariant that could not close. Recording the surface and the residue is the honest exit; further rounds would have kept finding spellings without ever reaching zero.
- Own the validator and its test together, because narrowing an acceptance carve-out is only safe with the mutation coverage that proves the committed fixture still passes.
- Use bounded parent implementation because this is a validation-authority path and writable delegation is prohibited for it.

## Tasks

- [x] Reproduce the admission read-only by splicing `sed -i "1r $root/AGENTS.md" "$update_source/NOTICE"` and `fixture_git "$update_source" add -- NOTICE` after the inventory loop and confirming the committed gate accepts it.
- [x] Bind the editing carve-out to the paths the inventory declares, and keep the committed fixture and its legitimate edit-then-stage sites accepted unchanged.
- [x] Add mutation coverage for an editing command that reads an out-of-inventory source, for an in-place edit of an undeclared path, and for the unchanged legitimate sites.
- [x] Close the first review round: read a staging written inside a called body, and bind the edit itself so a commit cannot carry an undeclared path into the tree.
- [x] Close the second review round: place a path the fixture reaches through the parameters a call site writes, so a helper function no longer hides the update source from every rule.
- [x] Close the third review round: union every readable call site, resolve a call-bound name recursively under a cycle guard, union the possible shift distances, and key the parameter cache on the reach it was resolved under.
- [x] Close the fourth review round: treat a guarded shift as uncertain, read a loop-carried shift as unbounded, and report a path operand this checker cannot place instead of accepting it.
- [x] Close the fifth review round: place loop variables and names that survive a call, and read only the operands a command actually writes, so the inverted disposition holds without a false rejection.
- [x] Close the sixth review round: stop the new command table from shadowing the copy commands the inventory region rejects, key each option table to the command that takes it, and read a call dispatched from a name this checker cannot place as assigning every name.
- [x] Close the seventh review round: classify an option after normalising the quoting of its name half, and report a staging that names no repository outside the directory it stands in.
- [x] Close the eighth review round: read a word one expansion away from a dash as an option this checker cannot name, and report a repository named relative to the directory the staging stands in.
- [x] Close the ninth review round: read a word an expansion opens as an unnameable option unless it carries a written path separator, and read every operand of a renaming or linking command so an alias of the update source is reported.
- [x] Complete one fresh independent read-only review and focused validation, and record every finding this plan's narrowed surface does not cover in the deferral backlog plan.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- The reproduction is recorded as High finding 1 of the Plan 247 independent review. It was confirmed again in this run against the committed gate with `tests/copier-update.sh` left byte-identical: splicing the `sed` and the staging after the inventory loop produced zero findings before the change and one `inventory_region` finding after it.
- The plan as written could not be implemented unchanged. Its original decision assumed the update source holds only the inventory-declared paths, but the fixture creates that directory with `git clone`, so it carries every tracked repository file. The committed fixture edits and stages `template/.project-agent-workflow/README.md`, which no inventory line declared. The owner approved declaring that path in the inventory and adding the inventory file to `write_scope` rather than weakening the invariant.
- A staging outside the inventory region is now accepted only when an editing operation writes the staged path and every path that operand settles to is declared by the inventory. A relative segment written with an expansion is read as undeclared, because the written text does not fix which file it names.
- The committed fixture stays accepted, and its four staging sites outside the region all name declared paths: `copier.yml`, `template/.project-agent-workflow/scripts/run-copier-update.sh`, `template/.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md`, and `template/.project-agent-workflow/README.md`.
- The first independent review returned two findings, both closed in this plan. A staging written inside the body of a called function was invisible, because the fixture reads a Git wrapper only at its call site; the staging read now falls back to the words such a body writes. A `git commit -a` or `git commit -- <path>` carried an undeclared path into the tree without touching a staging subcommand; the edit itself is now bound to the inventory, and the commit forms that stage on their own are read as a staging.
- The second independent review returned one finding: a helper bound from `$1` left the destination unplaceable, so the `named` gate skipped every rule before the inventory was consulted. It was reproducible against `HEAD` as well. The owner directed closing it inside this plan, which widened the change into the settling core.
- The committed fixture stays accepted with `tests/copier-update.sh` byte-identical to `HEAD`, and its lanes stay separate: `prepare_lane` is called only with literal lane names, none of which spells the update source.
- The third independent review returned two High and one Medium finding, all inside the new parameter model and all closed in this plan: one unreadable sibling call site discarded the readable ones, a name bound through a call was followed only one frame, a shift inside a conditional was counted as certain, and the parameter cache was keyed on the declaration alone.
- The fourth independent review returned three High findings, all closed in this plan: a shift guarded by `&&` was counted as certain, a shift a loop carries was counted once and its reader window ignored the loop-carried control flow, and an unplaceable destination word was still treated as harmless. The owner chose to close all three here rather than defer them.
- The fifth independent review returned one High and one Medium finding, both closed in this plan. The High was that the inverted disposition was scoped to positional parameters inside function bodies, so loop variables, `read`-assigned names, and expansion-modified names were still skipped; those forms were reproduced against `HEAD` as well, so this is pre-existing rather than a regression. The Medium was a false rejection this plan introduced in the fourth round, where a `sed` expression and a commit message were read as path operands.
- Removing the fifth-round guard on its own produced five false rejections in the committed fixture. Each one was diagnosed rather than suppressed: a name was discarded whenever any call to any declared function stood between its assignment and its reader, and copy sources and interpreter operands were read as written paths. Refining those three readings brought the committed fixture back to zero findings with the guard gone.
- Twelve evasion forms are now rejected, covering a wrapped staging, `git commit -a` and `git commit -- <path>`, a helper bound from `$1`, a shift guarded by `&&`, a loop-carried shift, a forwarded parameter list, a default-valued parameter, a loop-bound alias, and an unplaceable destination. Five legitimate forms stay at zero findings alongside the unmodified fixture.
- The sixth independent review returned three High findings, all regressions this plan introduced and all closed here. A second copy-command table shadowed the one the inventory region reads, removing a committed rejection of `ln` and `rsync` inside the region. The operand reading applied one option table to every command, so `sed -r` consumed the destination behind it and `cp -t DIR src` was read at the wrong operand. A call dispatched from a name this checker cannot place assigned nothing, so a callee reached through `$runner` could replace a settled name.
- The seventh independent review returned one High and one Medium finding, both closed here. Option classification ran on raw token text, so `"-t"`, `'-t'`, `-"t"` and `\-t` fell through to the operand list and the destination was dropped, which reopened a complete import-and-stage bypass at zero findings; a follow-up probe of my own found `cp "--target-directory=$where"` had the same shape. The Medium was a staging made invisible by a `cd`; the literal suggested form of that check produced nine false positives on the committed fixture, so it was closed at the staging instead.
- The eighth independent review returned two High findings, both closed here. `"-t$e"` defeated the option reading because the expansion escape hatch returned no name and the last-operand truncation then dropped the destination. `git -C .` defeated the new no-repository rule, because `.` and `./` settle to nothing rather than to a relative path.
- The ninth independent review returned two High findings, both closed here. `"${e}-t"`, `"$e-t"` and `"$opt"` normalise without a leading dash, so the truncation still dropped the destination; the suggested fix of treating every expansion as unreadable was measured and rejected, because it reports the committed fixture's own `cp "$root/pyproject.toml" "$root/uv.lock" "$tmp/copier-project/"`. A renaming or linking command gave the update source a second name in three lines of ordinary placeable shell at zero findings, because only its destination was read.
- Focused validation: 489 tests pass, `--check tests/copier-update.sh` passes, `scripts/check-copier-template.py` passes, and `git diff --check` reports nothing. `scripts/lint-project-workflow.sh` and `tests/smoke.sh` pass.
- Twenty evasion forms are now rejected, adding a quoted or escaped option name, an inline `--target-directory=` value, an option an expansion opens at either end or spells entirely, a repository named relative to the staging, a staging that names no repository, an indirect dispatch that replaces a settled name, and a symbolic link, hard link, or rename that aliases the update-source root. The unmodified fixture and every legitimate form stay at zero findings.
- Mutation coverage: disabling the inventory comparison, the body staging read, the call-site parameter binding, the reader-relative settling, the call-assignment refinement, the copy-operand reading, the interpreter exclusion, the loop-variable binding, the loop-head substitution rule, or the unplaceable-path report each fails the tests written for it. The later rounds add twenty more: restoring the shadowed copy table, un-keying each option table, dropping the indirect-dispatch reading, skipping the option-name normalisation, dropping the no-repository and relative-repository reports, reading only a literal leading dash, reading every expansion as unreadable, emptying the alias table, comparing only below the root, and truncating an alias command to its last operand.
- The tenth independent review returned two High findings, both deferred to `docs/plan/backlog/251-place-fixture-words-and-alias-sources.md` rather than closed here. An option written with its value in one word (`install "$topt$tmp/$lane"` with `topt=--target-directory=`) defeats the dash-word reading, because that word and the fixture's own `cp "$root/pyproject.toml"` have the same written shape; separating them requires placing the update-source root name, which is a parser capability this plan does not own. An inline interpreter program (`python3 -c "import os; os.symlink(...)"`) creates the alias without ever writing a shell command this reader can name, which no command-name rule can reach. Both were confirmed to be admitted by the gate committed before this plan, so the change remains a strict improvement.
- The review reported no regression from the ninth round: `tests/copier-update.sh` lines 377, 414, 423, 424 and 430 produce no new findings under all-operand reading of `mv`, the committed fixture stays at zero findings, and both pinned files stay byte-identical to `HEAD`.
- Ten review rounds is itself a defect in how this plan was run. The invariant as first written could not close, and the focused suite was run in full on every round when only five of its classes read the changed code; two unrelated classes carry 64 per cent of its 178 seconds. Later work on this checker should iterate on the classes that read the change and run the full suite once at the gate.
