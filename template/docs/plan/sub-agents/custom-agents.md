# Custom Agent Candidates

Use this file only when a repository repeatedly needs project-specific helper roles that are not covered by the generated defaults.

## Rules

- Prefer the generated `repo_explorer`, `evidence_synthesizer`, `fast_scoped_worker`, `scoped_worker`, `change_reviewer`, `docs_researcher`, and `sequential_plan_worker` roles first.
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

The generated `sequential_plan_worker` contract lives in `.codex/agents/sequential_plan_worker.toml`, routes writable work through `.project-agent-workflow/scripts/run-sandboxed-plan-worker.py`, and is governed by `.project-agent-workflow/docs/agent/SPEC_ORCHESTRATION.md`.
Do not redefine it here as a custom candidate.
