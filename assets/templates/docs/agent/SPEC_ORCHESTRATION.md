# Orchestration

The main agent owns task interpretation, integration, validation acceptance, planning updates, commits, and the final report.

## Helper Roles

- `repo_explorer`: read-only discovery and impact analysis.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness and regression review.
- `docs_researcher`: read-only external or version-specific research.

## Rules

- Delegate only bounded, independently useful tasks.
- Keep write scopes non-overlapping.
- Treat helper output as advisory until accepted.
- Prefer local work when coordination cost is higher than task complexity.

