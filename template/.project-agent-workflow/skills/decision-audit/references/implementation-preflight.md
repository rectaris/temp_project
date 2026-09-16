# Implementation Preflight

Read this reference when a task is about to move from deciding to doing: before
reopening a settled choice, before writing long plan prose, and after a formal
validation failure, or before broad integration when a material tool or current-system assumption is uncertain.

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

## Check Material Assumptions Before Integration

Start with the intended behavior and trace the current entrypoint, processing, state owner, consumers and retained behavior.
Name the repository evidence for that flow; an isolated function or a green unit test does not establish who owns the complete operation.
For each assumption that could invalidate the outcome, connect that flow to the adopted tool version's documented and observed behavior.
Select only relevant configuration, input/output, executable or module lookup, inherited environment, side effects and failure behavior; this is not a universal checklist.
Record the source revision or version for documentation and the exact command, inputs, directory and environment differences for observations, without recording secrets.
State what is documented, what was observed, what remains unknown, and which required behavior depends on the unknown.

When material uncertainty remains, run a bounded normal case and an assumption-breaking case before broad integration, within existing execution authority.
Choose the counterexample to challenge the assumption, not merely to repeat the successful path with different data.
Check the required output shape, destination, retained state and failure effect as applicable; a version string or successful exit alone is not proof.
Use a local synthetic input or disposable fixture when that safely answers the question.
If a probe needs unavailable access or expanded effects, keep the assumption unresolved and stop the dependent implementation rather than invent evidence or authority.
Keep this evidence in the existing task notes or local artifacts, not in a numbered investigation plan or a new form.
For mechanical work or an unchanged assumption already supported by applicable accepted evidence, skip extra probes and proceed through the existing validation.

## When Evidence Contradicts An Assumption

First identify the failed behavior and the premise it contradicts, without assuming every implementation error invalidates the design.
Code that violates a still-supported design takes the existing bounded correction path.
Evidence that refutes a design-critical assumption returns to normative decision audit before another patch.
Reconsider only the affected decisions and preserve the requirements, accepted safety conditions and external-effect authority.
After authoritative validation fails, record and preserve diagnosis_required before any repair classification; only its existing read-only reproduction and confirmed independent diagnosis path may proceed.
A new explanation or procedure improvement never reopens a stopped run or replenishes a review budget.
At task wrap-up, use `.project-agent-workflow/docs/agent/SPEC_TEMPLATE_FEEDBACK.md` for a reusable failed-assumption lesson; it grants no automatic persistence or publication.

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
