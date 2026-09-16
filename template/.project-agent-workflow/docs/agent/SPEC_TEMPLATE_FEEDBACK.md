# Template Improvement Records

## Purpose

A generated project records what the template did, what it needed instead, and what evidence supports that claim, without changing the product task that uncovered it.

Recording preserves observed facts and unresolved attribution. It grants no external effect, no network access, and no authority over the originating task.

## Configuration

`docs/agent/template-feedback.json` is project owned and holds a schema version, the project alias, and one mode.

`agent_select_local` lets the agent prepare a local draft on its own judgment. `disabled` makes every path a no-op.

Copier seeds this file from the chosen mode; updates preserve the project-owned value under the existing `docs/agent/**` rule.

## When To Prepare A Draft

At task wrap-up, prepare a draft only for an observed template workaround, a contradiction between template instructions, a repeated obstacle, or a concrete reusable improvement.

A task with no such finding prepares nothing, and so does a project in `disabled` mode. Neither is a failure.

Do not scan whole logs, environment files, or arbitrary project trees to look for material.

## Record Shape

A record names the report id, project alias, template source alias and revision, expected and observed behavior, impact, evidence, desired behavior, workaround, attribution, and any superseded report.

`template_source.revision` is an exact revision or the explicit value `unknown`. `attribution.certainty` is `template_defect`, `project_specific`, or `unknown`.

An unknown revision or an unresolved cause stays explicitly unknown. Do not infer either from the surrounding task.

Evidence items are agent-written paraphrases, synthetic reproduction steps, or reviewed repository-relative references. Each carries a bounded summary.

Records are immutable. A correction uses a new report id and names the earlier one in `supersedes`.

## Lessons From Failed Assumptions

Use the current record fields, not a separate report schema.
In `expected_behavior`, identify the assumption and the behavior it was meant to preserve.
In `observed_behavior` and `evidence`, describe the counterexample, its bounded reproduction and the actual result, separating documentation claims from observations.
Use `impact` for the affected behavior and `desired_behavior` for the next earlier check that would expose the assumption before broad integration.
Keep any temporary response in `workaround`, without presenting it as an accepted repair.

Distinguish an operating omission from a policy gap and a reproducible regression before choosing corrective action.
If existing guidance already required the missed check, describe how to apply that guidance earlier rather than adding a duplicate rule.
If the guidance omitted a material check, propose a bounded clarification in the existing policy or reference.
If a deterministic implementation defect violates the accepted behavior, propose a regression test and scoped repair through the existing task workflow.
These descriptions are evidence, not new attribution values: keep `attribution.certainty` and `template_source.revision` unknown when the cause or revision is not established.
One counterexample alone does not prove a generic template defect or that the proposed improvement will prevent future failures.
The existing draft eligibility, disabled mode, evidence review and separate task-bound persistence rules still apply; a lesson never continues stopped work.

## Evidence Safety

Select evidence explicitly and review the exact bytes before recording. Raw logs are never copied.

Every persisted text field is scanned, including each evidence reference, which stays a whitespace-free repository-relative location rather than a second prose field.

The command refuses obvious credential shapes. That refusal is a floor, not proof that reviewed text is safe to share, and automatic redaction is never the reason a record is acceptable.

## Commands

Use `.project-agent-workflow/scripts/template-feedback.py example` to print a complete record.

Use `check` to validate a record against the configuration and report the decision, the record path, and the checked digest.

Use `draft` to keep a validated record in the ignored local artifact tree; a draft is not a saved record.

Use `record` to persist a reviewed record under `docs/template-feedback/<project alias>/<report id>.json`. It requires the checked digest of the exact bytes it validates.

An identical repeat of an existing record changes nothing. Different bytes under an existing identity are refused.

## Task Boundaries

Persisting a record is a repository effect, so `record` runs under the shared task worktree guard like every other tracked write.

A product task does not save a record as a side effect. Prepare the draft, finish the product task, then record through a task binding that permits the write.

A blocked save leaves the draft in place. It never claims a saved record and never blocks the product conversation.
