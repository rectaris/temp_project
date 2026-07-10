# Custom Agent Candidates

Use this file only when a repository repeatedly needs project-specific helper roles that are not covered by the generated defaults.

## Rules

- Prefer the generated `repo_explorer`, `scoped_worker`, `change_reviewer`, and `docs_researcher` roles first.
- Add a custom role only after the repeated workflow, inputs, write scope, output contract, and validation expectation are clear.
- Keep helper output advisory until the main session accepts it through repository validation.
- Do not include secrets, unrelated local context, or external-service credentials in helper prompts.

## Candidate Template

```md
## <role-name>

purpose:
inputs:
write_scope:
output_contract:
validation:
fallback:
```

## sequential_plan_worker

purpose: implement exactly one assigned numbered active plan with bounded writes.
inputs: assigned plan, required specs, explicit write scope, and required validation commands.
write_scope: only the files explicitly assigned by the parent; never the plan lifecycle state.
output_contract: changed paths, implementation summary, validation results, blockers, cross-plan impacts, and remaining risks.
validation: run every validation command listed by the assigned plan.
fallback: stop and report when the write scope, required input, validation, or worker contract is unavailable.
