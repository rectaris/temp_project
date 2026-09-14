# Refuse the direct credential display forms an agent reaches for by mistake

status: in_progress
implementation_mode: parent_direct
primary_invariant: Each shell-command form this plan enumerates is refused before it runs when it would disclose a credential-named variable, and each form this plan enumerates as allowed still runs.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"An agent intending a presence test wrote a command whose second term used the default operator. That operator expands the value whenever the variable is set, so a live bearer token was printed into the session transcript and the owner had to regenerate it.","kind":"reproduced_defect"}
  - {"evidence":"Running the candidate forms under bash established that the alternate-operator form expands the value when its alternate text names the variable, so an exemption written for that operator alone would certify a bypass. The bracket-test form with a fixed-literal alternate reports presence for a non-empty value and absence for an empty or unset value without expanding it.","kind":"reproduced_defect"}
  - {"evidence":"A plain regex word boundary was tried against the incident variable and failed, because the underscore is a word character. Segment-aware matching does match it, but also matches ordinary names ending in a bare key segment, so the credential word list must exclude that segment rather than rely on boundary syntax.","kind":"reproduced_defect"}
  - {"evidence":"The pre-tool hardening gate already refuses commands through a tuple of compiled patterns, and already carries a secret-bearing file read rule, so an enumerated direct-display rule joins an existing refusal surface rather than adding one.","kind":"existing_mechanism"}
  - {"evidence":"check-external-service-policy.py already reads the external-services policy for both schema versions without PyYAML, so the hook can reuse that reader instead of adding a runtime dependency a generated project may not have.","kind":"existing_mechanism"}
  - {"evidence":"check-copier-template.py compares the root and generated pre-tool gates after their bootstrap import and fails when they differ, so both copies must change together and both belong in the write scope.","kind":"existing_mechanism"}
completion_conditions:
  - Every refused form named in the enumerated list is refused when its variable is credential-named.
  - A bare environment dump is refused even though it names no variable.
  - The bracket presence test with a fixed-literal alternate still runs, and so does passing a credential in an outbound request header and in a child process environment assignment.
  - A name whose only credential-like segment is a bare key segment is not treated as credential-named, while the incident variable is.
  - A missing or malformed external-services policy leaves the name-based refusals working and refuses no unrelated command.
  - The root and generated gate copies stay identical after their bootstrap import.
completion_witness_map:
  - {"condition_sha256":"sha256:f796cd06e6b8694f6752a0494761d41da6a036badba6925953e5b05e81bf9341","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:4d6e702cfac61aeb6d44249552598f963503596cda923f16ee8efe1f8e139d8f","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:5e8411125b84576b880b90b11a201a98876f4a722ba65a7699fa2ce0748070e7","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:b4180e7f28f10226ba066e28c895df0e33190b5e8ee63b6c8fd3e747ee7a7e82","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:9f148055b567318fc9d8feab6fedafd94c89f9a1376c4201bf634b06d40d32cb","witness":"python3 tests/test-hooks.py"}
  - {"condition_sha256":"sha256:15261435ab4627e262676f760bfdf122da0ab5e9db02017792c1d0d28ba1f57a","witness":"python3 tests/test-copier-fixture.py"}
write_scope:
  - template/.project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - .project-agent-workflow/hooks/pre_tool_hardening_gate.py
  - template/.project-agent-workflow/scripts/security_rules.py
  - tests/hooks/gates.py
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_SECURITY.md
  - template/.project-agent-workflow/scripts/check-external-service-policy.py
  - scripts/check-copier-template.py
  - template/.codex/hooks.json.jinja
required_specs:
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
focused_validation:
  - python3 tests/test-hooks.py
  - python3 tests/test-copier-fixture.py
validation:
  - python3 tests/test-hooks.py
  - python3 tests/test-copier-fixture.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The default-operator form that caused the incident is refused, and so is a bare expansion of the same variable inside an enumerated display command.
  - The alternate-operator form is refused when its alternate text is anything other than a fixed literal, because that form can disclose the value.
  - A bare environment dump is refused, and a targeted environment read naming a credential variable is refused.
  - The bracket presence test with a fixed-literal alternate still runs, an outbound request carrying the credential in a header still runs, and a child process environment assignment still runs.
  - The incident variable is classified as credential-named, while an ordinary name whose only credential-like segment is a bare key segment is not.
  - A variable named only by the external-services policy is refused, and a missing or malformed policy refuses no unrelated command.
  - The root and generated gate copies remain identical after their bootstrap import.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:7bc35d7f6a7a9775e312f9107856d1c59cded42cf930195b2afe0c348a8660cb","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:786a2a82c2c9cab1f5d53fa3678a88dbcf94081a809fe68c5038ec69c7672cfb","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:c0bf47ed9471d989d3941ba0ebabc6cdd960f7eff5202df2b10531f2abda4c25","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:816f78cf9ee2dce8d637b890cce060b45998726c8aa9f41a31af6e26586a6f41","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:9b717007a82cb1061401181a8297821611bf8d45046230bf3dff0ba06f1235fa","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:bc2a3ae6a33d15fad66140497f455943ed2897fd2ed948cadd3d4570fc959b3f","stage":"focused","witness":"python3 tests/test-hooks.py"}
  - {"acceptance_sha256":"sha256:875bde8510d76428639028d7f7eca9bc7384541987831f6c3b9fcea745331600","stage":"focused","witness":"python3 tests/test-copier-fixture.py"}
checked_summary_ja: 認証情報をそのまま表示する、誤って書かれやすい形を実行前に拒否する。

## Decisions

- State the invariant over an enumerated list of command forms rather than over all shell output, because shell disclosure depends on parsing, redirection, tracing, and child-process behaviour that a pattern cannot decide. This control prevents the high-confidence accidental forms; it is not a sandbox.
- Name the refused commands as a closed list of command heads rather than describing them by purpose, because a category such as a command that displays text is not decidable and would put the plan back where the review found it.
- Refuse the alternate-operator form unless its alternate text is a fixed literal, because running it under bash showed that an alternate naming the variable discloses the value, so exempting the operator wholesale would certify a bypass.
- Enumerate a bare environment dump separately from the targeted forms, because it discloses every variable while naming none, so a rule keyed on a credential name would miss it.
- Classify names by underscore-separated segments and exclude a bare key segment from the credential word list, because a plain word boundary misses the incident variable while segment matching on a bare key segment refuses ordinary names, and the refusal cannot be overridden.
- Extract credential names from schema version one services that read their credential from the environment, and accept that schema version two declares no credential variable, so version two contributes names only if a later schema adds them.
- Treat an absent or malformed external-services policy as contributing no names, because failing closed there would refuse unrelated commands in every project that lacks the file.
- Change both gate copies in one plan, because the template consistency check compares them after their bootstrap import and a single-copy change fails that check.
- Own the credential-name classifier here and expose it for reuse, but do not promise that the command-form pattern is reusable against file contents, because the two inspect different things.

## Tasks

- [ ] Define the credential-name classifier in the shared security rules module: split a candidate name on underscores and treat it as credential-named when a segment matches an unambiguous credential word, when it matches a two-segment credential phrase, or when the external-services policy declares it. Exclude a bare key segment from the unambiguous word list.
- [ ] Read the external-services policy through the existing PyYAML-free reader, resolved from the installed hook's repository root. Take credential variable names from schema version one services whose authentication reads the environment. Treat a missing, unreadable, or unsupported-version policy as contributing no names.
- [ ] Enumerate the refused forms as a closed list of command heads and expansion shapes, with no category defined by purpose. Cover: an enumerated display command whose arguments expand a credential-named variable in any form other than a fixed-literal alternate; a targeted environment read naming a credential-named variable; a bare environment dump; and a shell builtin that prints variable definitions.
- [ ] Enumerate the allowed forms with equal precision: the bracket presence test with a fixed-literal alternate, a credential expanded into an outbound request header, and a child process environment assignment.
- [ ] Add the rule to both the root and generated gate copies so the template consistency check keeps passing. The root gate imports the shared rules module from the template tree, so the pattern itself is defined once.
- [ ] Extend tests/hooks/gates.py with every refused and allowed form this plan enumerates, including the alternate-operator bypass, the bare dump, the incident variable, an ordinary name ending in a bare key segment, a policy-named variable, and an absent policy.
- [ ] Measure the added latency per invocation in milliseconds and record it, because the configured hook timeout is too coarse to detect a per-call cost.

## Validation Notes

- Baseline recorded before implementation: tests/test-hooks.py and tests/test-copier-fixture.py pass on the unchanged checkout.
- Residual exposure this control does not prevent: command substitution that renames the value, indirect expansion, eval, language-runtime reads of the environment, shell tracing, partial or encoded disclosure, a credential whose name is neither policy-declared nor credential-like, and any command head outside the enumerated list. These stay outside the enumerated list on purpose and are recorded here rather than implied away.
- Known false-negative accepted by the word-list decision: a credential variable whose name ends in a bare key segment and is not declared by the external-services policy is not classified as credential-named. Declaring it in the policy is the supported remedy.
