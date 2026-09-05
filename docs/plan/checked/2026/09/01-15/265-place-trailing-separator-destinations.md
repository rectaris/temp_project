# Report a directory destination written with a trailing separator

status: checked
primary_invariant: when a non-deferred cp or install has at least two operands and no option form other than an optional leading literal -- terminator, and its final operand has at least one fully resolved form through ordinary path bindings with every form ending in a literal path separator, the focused checker places each settled source basename or nonempty literal written suffix other than . or .. below every resolved destination and treats an unavailable source basename as an unplaceable write without changing any other command form
task_types:
  - template_workflow
  - security
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"kind":"reproduced_defect","evidence":"At a60a0c7, cp or install \"$root/AGENTS.md\" \"$tmp/update-source/\" returns zero findings, while cp or install with \"$tmp/update-source/AGENTS.md\" returns two inventory_region findings."}
  - {"kind":"bounded_prototype","evidence":"At a60a0c7, a path-only prototype using _word_parts with splits=True and allow_equals=False plus _resolve_parts with fixture.bindings_for(operation) preserves the final slash for slash=/ followed by \"$tmp/update-source$slash\", while e= followed by \"$e$tmp/update-source/\" remains unresolved instead of receiving the empty-only value reserved for option classification."}
  - {"kind":"existing_mechanism","evidence":"The _helper_paths target-directory-option branch already falls back to _written_name(source.text) when a source path does not settle; the ordinary last-destination branch currently omits that fallback."}
completion_conditions:
  - For a non-deferred cp or install with at least two operands and no option form other than an optional leading literal -- terminator, a final operand with at least one fully resolved form whose forms all use ordinary path bindings and end in a literal path separator is treated as a directory, and every settled source basename is reported below every resolved destination.
  - Separator detection never uses _option_bindings, so an empty-only assignment, an unresolved value, or mixed trailing and non-trailing forms cannot establish directory placement and retains its existing disposition.
  - When an eligible source path does not settle, only a nonempty literal written suffix other than . or .. is placed below the destinations; any source without such a basename makes the directory write unplaceable.
  - A bounded differential corpus has no reject-to-accept transition, no accept-to-reject transition outside the declared cp and install cases with either no option or a leading literal -- terminator, and no new exception.
  - The -T, --no-target-directory, --parents, install -d, install -D, target-directory-option, unresolved-option, deferred-operation, mv, and ln controls retain their prior dispositions and gain no synthesized inside pair.
  - tests/copier-update.sh is byte-identical to the implementation source HEAD.
  - The committed tests/copier-update.sh fixture passes the focused checker with zero findings.
completion_witness_map:
  - {"condition_sha256":"sha256:4675d623f4f69df78bd4f2917a48c40da4ce18d201f47bd888c1e50458f525be","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:177665a711a1f1db1a714c07c4f0c4a5c08c72e505116946dd49ceeb265bae62","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:8b3d929ae98aa0b4c6ca9f9b110c4d4038a78cc6489233893f565ab33e36ec15","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:c5b04c12d5b3a605292300e6413a68beb823fc8a52c50b0a197f8a09e242bc46","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:d41cd47e715d7d26404fe9bf3186775e3ef4e9e5854ae5ceff17f0272fb71887","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"condition_sha256":"sha256:0865bbf73e1698205f46f91710776ec0b268b7d33253e415fd525372dcecd69b","witness":"git diff --exit-code HEAD -- tests/copier-update.sh"}
  - {"condition_sha256":"sha256:d4be619e5b03795cb3c21aceb9082620cb365e4444cf00b67b744548919a4891","witness":"python3 scripts/project_workflow/copier_fixture_validator.py --check tests/copier-update.sh"}
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
  - docs/plan/checked/2026/09/01-15/251-place-fixture-words-and-alias-sources.md
  - docs/plan/checked/2026/08/16-31/248-bind-fixture-editing-to-the-inventory.md
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
  - git diff --exit-code HEAD -- tests/copier-update.sh
  - git diff --check
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - For a non-deferred cp or install with at least two operands and no option form other than an optional leading literal -- terminator, use only ordinary path bindings to treat a final operand as a directory when it has at least one fully resolved form and every form ends in a literal path separator, and place each settled source basename or nonempty literal written suffix other than . or .. below every resolved destination.
  - Fail closed when an eligible directory write has an unavailable source basename, and preserve every command form outside that declared boundary.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:2e3aca7915825b2d35dd3acba3539cf561c1e7778b20224472739f014f1d6c04","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
  - {"acceptance_sha256":"sha256:457ad46bb438bf38425ab4b419fec1d2888584279367be42a19dff3d86f6c6e7","stage":"focused","witness":"python3 tests/test-copier-fixture-validator.py"}
predecessor_plans:
  - docs/plan/checked/2026/09/01-15/251-place-fixture-words-and-alias-sources.md
integration_gates:
  - do not edit, stage, or commit tests/copier-update.sh in this plan; the committed fixture is the read-only subject under test
  - compare the exact activation HEAD with the candidate over a deterministic matrix of cp, install, mv, ln, option classification, separator resolution, and source-name resolution; admit only the declared new cp and install findings and no new exception
  - keep every existing rejection passing, keep every non-target acceptance passing, and keep option-bearing and target-directory-option paths unchanged
checked_summary_ja: option を持たない cp と install の宛先を通常の path binding だけで解決し、すべての候補が末尾セパレータを持つ場合に、空でなく . や .. でもない source basename を各宛先の配下へ配置する。

## Decisions

- Derive separator evidence for non-deferred operations in a new path-only helper by passing `_word_parts(..., splits=True, allow_equals=False)` to `_resolve_parts` with `fixture.bindings_for(operation)` and `fixture.unsettled_for(operation)`. Do not call `_resolved_word_parts` or `_option_bindings`: the empty-only values supplied there are reserved for option classification and must never settle a path or establish its separator.
- Apply the new placement only when the resolved command is `cp` or `install`, at least two operands remain, and either the first post-command word is the literal `--` terminator or every post-command word is proved not to be an option. A word is proved not to be an option only when `_resolved_word_texts` returns bounded texts that are all `-` or do not start with `-`, or `_cannot_name_an_option` proves the word carries a slash or an anchored path. Use those existing option-classification helpers only for this eligibility decision; they cannot supply path parts. `-T`, `--no-target-directory`, `--parents`, `install -d`, `install -D`, target-directory options, unresolved or mixed option words, and a `--` written after an operand are outside this rule and keep their existing dispositions.
- Require the path-only helper to return at least one fully resolved destination form and every form to end in a literal path separator before removing that separator for path placement. An empty-only assignment, an unresolved value, and mixed trailing and non-trailing forms do not prove this condition.
- For a settled source, retain every existing final path segment. When a source path does not settle, reuse `_written_name(source.text)` without changing that shared helper, and accept its result only when it is nonempty and differs from `.` and `..`; otherwise mark the known directory write unplaceable so the existing fail-closed finding reports it.
- A deferred operation or destination word that does not satisfy every boundary above keeps its existing reading. Do not change `mv`, `ln`, target-directory-option handling, or any option-bearing `cp` or `install` form.
- Use bounded parent implementation because both write-scope paths are validation authority and the writable runner refuses them. Require an independent read-only review before authoritative validation.

## Tasks

- [x] Reproduce the direct and ordinary-assignment-resolved trailing-separator admissions at the exact activation HEAD, record the findings and `_helper_paths` outputs, confirm that `tests/copier-update.sh` is byte-identical, and show that an empty-only assignment does not settle through the path-only prototype.
- [x] Add the path-only separator helper and invoke it only for the bounded option-free or leading-`--` command forms, reuse the valid written-name fallback for each unsettled source, and mark the write unplaceable when no valid basename is available.
- [x] Add `InventoryRegionTest` coverage for direct and ordinary-assignment-resolved separators, a leading literal `--`, multiple source operands, an unavailable or expansion-ended source basename, source suffixes `/.` and `/..`, empty-only and unresolved bindings, mixed separator forms, the no-separator and explicit-filename controls, an outside directory, and unchanged `mv` and `ln` behavior.
- [x] Add regression coverage proving that `-T`, `--no-target-directory`, `--parents`, `install -d`, `install -D`, target-directory options, an unresolved option word, a `--` after an operand, and a deferred operation remain outside the new rule with their prior dispositions and no synthesized inside pair.
- [x] Compare the activation HEAD and candidate over the bounded matrix declared by the integration gate, and record every disposition change and exception count.
- [x] Complete one independent read-only review and focused validation with zero unresolved High or Medium findings.
- [x] Archive and commit only the declared write scope plus parent-owned lifecycle files.

## Validation Notes

- Pre-activation reproduction at `a60a0c7` confirmed zero findings for the direct `cp` and `install` trailing-separator forms and two `inventory_region` findings for their explicit-filename controls.
- `_helper_paths` returns no inside pair for the corresponding `mv` form either; its two findings come from alias and unplaceable-operand rules, so `mv` is a regression control rather than the implementation model.
- The activation HEAD for this run is `95cbf2c`. The reproduction holds there unchanged: `cp "$root/AGENTS.md" "$tmp/update-source/"` and the `install` spelling produce zero findings, while their explicit-filename controls produce two `inventory_region` findings each.
- The separator is read by the new `_path_forms`, which resolves the destination word through `_word_parts(..., splits=True, allow_equals=False)` against `bindings_for` and `unsettled_for`. `_settled_path` drops the empty segment a trailing separator writes, so the settled destination alone cannot carry that evidence and the resolved parts are read instead.
- The path reading never takes the empty value option classification supplies. With `empty=` in scope, `_resolved_word_texts` returns `"/dest/"` for `"$empty/dest/"` while `_path_forms` returns nothing, so that destination keeps its fail-closed disposition.
- One resolved form that writes no separator defeats the directory reading. Two call sites passing `"two/"` and `two` leave the destination read as a file, while two call sites passing `"two/"` and `"three/"` place the source below both resolved destinations.
- A source that settles keeps its settled final segment. A source that does not settle is placed under `_written_name`, accepted only when it is nonempty and neither `.` nor `..`; a source ending in `.`, `..`, or an expansion makes the directory write unplaceable, which the existing fail-closed finding reports.
- Differential evidence against the activation HEAD over the declared matrix of `cp`, `install`, `mv`, `ln`, option classification, separator resolution, and source-name resolution: the only disposition changes are the declared `cp` and `install` forms written with no option or a leading literal `--`. No fixture rejected before is accepted now, and no new exception is raised. The `-T`, `--no-target-directory`, `--parents`, `-R`, `install -d`, `install -D`, `-t`/`--target-directory`, unresolved-option, `--`-after-operand, deferred, `mv`, `ln`, `touch`, and `tee` controls are byte-identical, and `cp SRC DIR` without a separator is unchanged.
- The independent read-only review measured 609,700 `_helper_paths` cases across commands, option forms, sources, destinations, preludes, and enclosing wrappers. `created` and `words` were identical in every case, `inside` never shrank, and `unknown` was never cleared, so the change is monotone in the fail-closed direction and can produce no reject-to-accept transition.
- That review reported no High and no Medium finding. Its three Low findings were test-quality only and were remediated in the same write scope: the deferred control now discriminates the deferred guard, the multiple-source case now uses two unsettled sources so it fails at the activation HEAD, and `install -d` gained a two-operand spelling that reaches the option gate. Each remediation was mutation-checked, and removing the deferred guard now fails exactly one test.
- Focused validation: `python3 tests/test-copier-fixture-validator.py` runs 563 tests OK, `copier_fixture_validator.py --check tests/copier-update.sh` passes with zero findings, `scripts/check-copier-template.py` passes, `git diff --exit-code HEAD -- tests/copier-update.sh` is clean, and `git diff --check` is clean. The committed fixture was never edited, staged, or committed by this plan.
- Authoritative validation: `scripts/lint-project-workflow.sh` and `tests/smoke.sh` pass.
- One authoritative lint run failed in `tests/test-human-report.py` at a whole-second timestamp boundary. Bounded read-only diagnosis reproduced the same failure at unmodified `95cbf2c` in a separate worktree at one failure in twenty-five runs, and its subject `template/.project-agent-workflow/scripts/human-report.py` is untouched by this change. The failure is pre-existing and outside this plan's `write_scope`, so it is reported rather than repaired here.
