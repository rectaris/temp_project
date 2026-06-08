# Orchestration

The main agent owns interpretation, final integration, validation acceptance, planning updates, and commits.

## Helper Roles

- `repo_explorer`: read-only file discovery and impact analysis.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness, regression, validation, and security review.
- `docs_researcher`: read-only external or version-specific research.

## Delegation Rules

- Delegate only concrete, bounded, independently useful work.
- Assign non-overlapping write scopes.
- Keep final judgment in the main session.
- Treat helper output as advisory until accepted through validation.
- Use durable handoff files only for cross-session transfer or staged work.

## Cost Gate

Use local execution for tightly coupled, urgent, or small work. Use helpers when context pressure, file size, semantic risk, or review value outweighs coordination cost.

