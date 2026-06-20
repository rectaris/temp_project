# Orchestration

The main agent owns task interpretation, integration, validation acceptance, planning updates, commits, and the final report.

## Helper Roles

- `repo_explorer`: read-only discovery and impact analysis.
- `scoped_worker`: bounded implementation with explicit write scope.
- `change_reviewer`: read-only correctness and regression review.
- `docs_researcher`: read-only external or version-specific research.
- Project-specific helper templates may live under `docs/plan/sub-agents/` when repeated workflows justify them.

## Rules

- Delegate only bounded, independently useful tasks.
- Keep write scopes non-overlapping.
- Treat helper output as advisory until accepted.
- Prefer local work when coordination cost is higher than task complexity.
- Keep final interpretation, integration, validation acceptance, planning updates, commits, and completion reports in the main session.
- Use durable handoff directories only when direct helper output is not enough for continuity or review.

## Command Sessions

- Use normal command execution for short, deterministic commands.
- Use tmux when available for long-running commands, shared processes, watch tasks, dev servers, and interactive CLIs.
- Name tmux sessions descriptively enough that another agent or a human can identify the task.
- Capture logs to a project-local file when command output may be needed after the session ends or by another agent.
- Before starting a duplicate long-running process, check for an existing relevant tmux session.
- When human intervention is needed, report the attach command instead of re-running or abandoning the process.
- Stop tmux sessions that are no longer needed unless the user asked to keep them running.

## Decision Matrix

- Use local execution for urgent critical-path work, direct user clarification, final specification judgment, validation acceptance, planning updates, commits, and completion reports.
- Use `repo_explorer` for targeted discovery, impact analysis, and existing-pattern lookup.
- Use `scoped_worker` for bounded implementation when write scope is explicit and non-overlapping.
- Use `change_reviewer` for correctness, regression, validation-gap, security, and spec-conflict review.
- Use `docs_researcher` for official, external, version-specific, or API facts that may have changed.

## Context Pressure

Consider delegation or a separate review when:

- a single file is large or semantically dense
- source/spec reconciliation is required
- a change touches data and runtime logic
- a change affects validation rules, hooks, security checks, or orchestration
- repeated low-level lookup would distract from final integration

## Stop Review Gate

- A deterministic Stop hook may request a final review pass for broad or high-risk diffs.
- Treat the hook as a review prompt, not a validation runner.
- If the requested helper path is unavailable, use the closest read-only review path and record any validation gap.

## Fallback

- Tool availability is not assumed.
- Choose fallback by the original task purpose, not by a fixed global ranking.
- External helpers are optional and advisory.
- Do not include secrets, credentials, or unrelated local context in helper prompts.
