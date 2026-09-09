# Implementation Preflight

Read this reference when a task is about to move from deciding to doing: before
reopening a settled choice, before writing long plan prose, and after a formal
validation failure.

Project policy is normative. `.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md`,
`.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md`, and `.project-agent-workflow/docs/agent/SPEC_SECURITY.md` decide
every question this reference touches. This reference adds no authority: it
grants no independent diagnosis, no independent repair, no numbered
investigation plan, no parallel execution, and no external write.

## Accepted Decision Reuse

Identify the requested outcome first, then the evidence that a decision is
already accepted. Accepted evidence is a checked plan record, the `## Decisions`
section of the authorized active plan, or an explicit owner instruction.

Reuse an accepted decision without a new audit and without new approval while
all of the following hold.

- The requirement is unchanged.
- The accepted safety conditions are unchanged.
- The class of external effects is unchanged.
- The authority that approved it is unchanged.

If the decision record cannot establish any one of these four conditions, do not reuse the decision; treat it as not yet made and run the decision audit.

A new plan id, a routine checkpoint, a resumed session, or a skill invocation
does not by itself make a settled choice open again.

Require explicit authorization again, and stop until it arrives, when any of the
following is true.

- The requirement itself changed.
- An accepted safety condition changed.
- External effects expanded, including a new destination, a new credential
  class, or a first write to a service previously used read-only.
- A stopped run would be continued.

Separate a request to repair the product from a request to improve the
development procedure. A procedure request authorizes plan authoring, not
product implementation, and never continues an unrelated stopped run.

## Requirement, Scope, Condition, And Witness Preflight

Run this preflight before writing long plan prose, not after.

Use the repository's existing shared plan authoring check rather than a new
form. Both the root and the generated plan creation commands route into
`plan_authoring.py`, which derives the correspondence and the digests.

Confirm each of the following before the prose grows.

- Requirement: every user requirement maps to one acceptance item.
- Scope: every file the change must touch is inside `write_scope`, including the
  root and generated counterparts and the files that register new tests.
- Condition: every completion condition is plan-local, bounded, and checkable.
- Witness: every acceptance item binds exactly once to a command already named
  in `focused_validation` or `validation`, at its earliest honest stage.

A missing counterpart, an unregistered test file, or an acceptance item with no
witness is a preflight failure. Fix the manifest first. Do not open a numbered
feasibility plan to answer a preflight question.

## Exact Failure Reproduction

After a formal validation failure, `diagnosis_required` is already in force.
Preserve it. Do not classify a repair, request a correction, run validation
again, apply a candidate, complete a plan, or archive anything while it holds.

Reproduce the exact failure before proposing anything.

- The exact command that failed, with its exact arguments and flags.
- The exact working directory, and whether it was the task worktree, a generated
  project, or a temporary clone.
- The exact input the command read, including the committed revision when the
  command builds its source from a clone at `HEAD`.
- The observed exit status and the first failing assertion, by file and line.

State whether the failure belongs to the template development repository or to
the generated project. These two are routinely confused because their paths
differ only by the managed workflow directory prefix, and a fix applied on the
wrong side leaves the real defect in place.

Only a confirmed diagnosis with an independent-review receipt may leave
`diagnosis_required`, and only into the existing `repair_required` or
`replan_required` classification. Inconclusive evidence stays stopped.

When an execution budget is exhausted rather than a defect being found, stop for
an owner decision. Do not create a repair, descope, or reconstruction successor
merely to reset a review or correction budget.
