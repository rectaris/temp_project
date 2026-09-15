# Refuse a staged review whose runtime evidence observes no reviewer tool call

status: backlog
primary_invariant: A staged review is admitted only when the runtime evidence already bound to it observes at least one tool call in the reviewer session.
task_types:
  - validation_tools
  - planning_docs
review_class: A
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: high
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Recorded in the plan 376 session feedback draft: a synchronous review helper returned a no-issues answer with zero file-reading tool calls. The parent could refuse it only by its own judgement, because no admission path in scripts/plan-execution-state.py reads a reviewer tool-call count.","kind":"reproduced_defect"}
  - {"evidence":"validate_resource_observations in scripts/plan-execution-state.py already requires a bounded resource_observations object whose metrics include tool_call_count, already rejects an observed metric that carries no bound evidence digest, and already rejects an unavailable metric that claims a value.","kind":"existing_mechanism"}
  - {"evidence":"review_turn_zero_from_manifest already loads the same run manifest through resource_observations_from_manifest when it admits a staged review, so the metric is read where the review is admitted and this plan adds no new evidence source.","kind":"existing_mechanism"}
  - {"evidence":"A plain parent_review that binds no review target skips the staged branch in read_state, so an added staged condition leaves the legacy route and the forty existing records untouched.","kind":"existing_mechanism"}
completion_conditions:
  - A staged review is refused when the run manifest bound to it reports the reviewer tool-call count as not observed or as zero.
  - A staged review whose bound run manifest observes at least one reviewer tool call is admitted with its existing behaviour unchanged.
  - A plain parent review that binds no review target keeps its existing behaviour, and every execution ledger the repository already holds keeps verifying without being edited.
  - The template copy of the execution state command stays aligned with the root copy.
  - The plan workflow specification states that an admissible staged review requires at least one observed reviewer tool call, and the root and template copies stay aligned.
completion_witness_map:
  - {"condition_sha256":"sha256:95f516341c725feadbe1cf9a77582ad38741fe8b111a48766dc2e30d1b941681","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:7aa6754982ee6a70b1a1aa29153fc8957ec8ffb35680f216dae5b11e923b764e","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:d039860ea0a3d4b47f8558d67fdc4804a041239538594f3fb5bff05a6459679a","witness":"python3 tests/test-plan-execution-state.py"}
  - {"condition_sha256":"sha256:82520db89dd050db33055d16295bd4022d35a8b4390c1ed3c3e7fa8855444e75","witness":"python3 scripts/check-copier-template.py"}
  - {"condition_sha256":"sha256:946766f0a5ed52eb42acce28f652caf879449cc12b2a2adbfc831d84428841a0","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/plan-execution-state.py
  - template/.project-agent-workflow/scripts/plan-execution-state.py
  - tests/test-plan-execution-state.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - scripts/check-agent-log-manifest.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_SECURITY.md
focused_validation:
  - python3 tests/test-plan-execution-state.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - A staged review whose bound runtime evidence observes no reviewer tool call is refused.
  - A staged review whose bound runtime evidence observes at least one reviewer tool call is admitted.
  - The plain parent review route and every existing execution ledger are unchanged.
  - The root and template copies of the command stay aligned.
  - The authoritative suite passes with the added admission condition in place.
  - Both copies of the plan workflow specification state the reviewer tool-call requirement.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:04dbb795b84715efa21c357ddb1f432e54c8899576b447a9e49f2ae613dd8d4a","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:456bb1e1294613336bf9a9a6a6c97fa6a9e8bfd773d8298a8b98fcd849d11b40","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:10b751f76e9831c8b4cc592dc29dfe8cc33a24b9114e5411dcda571325b95091","stage":"focused","witness":"python3 tests/test-plan-execution-state.py"}
  - {"acceptance_sha256":"sha256:14adefe88021f6d209181bb6bc0da6db7630cf2bdc240c55f96a0c6dcc5fddb0","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
  - {"acceptance_sha256":"sha256:703ed8f2ebe5512cd94aa871ea601a5ef97bfbc0810e0d24bd170e25fba21f64","authoritative_only_reason":"The generated project's own copy of the command is only executed by a full generated project, which no narrower command builds.","stage":"authoritative","witness":"tests/smoke.sh"}
  - {"acceptance_sha256":"sha256:4aebf9f65e073434f60172be30937f237971571d7832abfb8bc95b7080d61aef","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
checked_summary_ja: レビューアのツール呼び出しが観測されない段階レビューを拒否する。

## Decisions

- Set the threshold at one observed tool call. The observed failure was a review that read nothing, so the condition refuses exactly that case and makes no claim about how much reading a review needs.
- Read the count from the run manifest the staged review already binds. A separate reviewer-supplied number would be a self-report, and the manifest metric is already bound to the digest of the evidence file that produced it.
- Treat a not observed count as a refusal rather than a pass. A route that cannot report reviewer tool calls cannot show that the review read anything, and admitting it would return the gate to the reviewer's own word.
- Leave the plain parent_review route untouched. It binds no review target and is the bootstrap route the packet-start plan needs, so changing it here would couple two independent invariants.
- Record the rule in the plan workflow specification rather than the logging specification. The logging specification owns what a manifest may observe; this rule is about what a review admission requires.

## Tasks

- [ ] Confirm the write scope and the current required specifications, then reproduce a staged review admission with a manifest whose tool-call count is zero, using the committed test fixtures.
- [ ] Read the bound run manifest's reviewer tool-call metric where the staged review is admitted, and refuse a count that is not observed or is zero.
- [ ] Confirm that the plain parent review route and the existing ledgers are unaffected.
- [ ] Add the refusal, admission and legacy cases, and confirm each fails when its production line is reverted.
- [ ] Mirror the command into the template and record the rule in both copies of the plan workflow specification.
- [ ] Run the focused validation, then run the authoritative suite once on the final candidate.

## Validation Notes

- This plan is independent of the packet-start producer plan. It can be checked with the existing test fixtures, which already build run manifests, and it does not need a real reviewer session.
- Ordering still matters in practice: until the packet-start producer exists, no staged review reaches this condition, so the gate is latent rather than active on the day it is checked.
