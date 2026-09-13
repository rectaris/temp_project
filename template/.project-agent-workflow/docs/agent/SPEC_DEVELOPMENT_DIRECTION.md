# Development Direction

## Purpose

The development direction states what this repository has decided to build next, and it rests on nothing else.

Every entry traces back through an explicit decision to the exact requirement bytes that decision approved, and from there to the reports that raised it.

## Decisions

A decision lives under `docs/improvements/decisions/<decision id>.json` and names the candidate it decides, the exact candidate digest, the action, the reason, the ordering priority for an adopted requirement, the authority it rests on, and the implementation and downstream-verification evidence.

An action is `accept`, `defer`, or `reject`. Only an accepted requirement carries a priority.

The history is append-only. Repeating one decision unchanged does nothing; different bytes under a held id are refused, and a changed decision arrives as a new decision id that supersedes the earlier one. Two live decisions about the same candidate revision are refused unless the later one explicitly supersedes the earlier, even when they agree, because one requirement carries one decision. A supersession replaces an earlier decision about the same requirement; it cannot reach across to retire a decision about a different one.

## The Command Checks Shape, Not People

`authority` records the instruction a decision rests on: `owner_instruction` with a bounded quotation, or `prior_authorization` with the exact earlier decision it relies on.

The command validates that shape. It cannot authenticate a person from free-form text, and it never treats a report, a candidate, a supplied quotation, or a claimed approval field as authority.

Before invoking a decision write, verify the actual owner instruction in the current session, or resolve an exact earlier authorization that already covers this requirement revision and this effect. Refuse an unsupported claim; a fabricated quotation is a fabricated decision.

## A Changed Requirement Is a New Decision

Each decision binds one candidate digest. When a candidate is revised, the decision on the earlier bytes becomes historical and the new bytes carry no decision until someone makes one.

Approval is never transferred silently, and history is never erased. `render` and `inspect` both keep superseded, orphaned, and invalidated decisions visible with the reason they stopped applying.

## Rendered Document

`render` writes `docs/development-direction.md`, replacing only the region between the generated section markers.

Prose outside that region is yours and is preserved exactly. A document with missing, duplicated, or out-of-order markers is refused rather than repaired by guesswork.

Imported prose is evidence inside the document, never structure. Text that arrived from a downstream report is written as a single line and may not contain a section marker; a requirement whose text would break that rule is listed as not rendered, with the reason, instead of being placed in the document. So a report cannot forge a heading, an adopted entry, or a section boundary that nobody decided, and it cannot leave the document unrenderable afterwards.

The generated region lists adopted requirements in priority order with their reasons, completion criteria, unresolved questions, recorded disagreements, and source reports, then deferred and rejected decisions, then suggestions nobody has decided, then the historical decisions and the reason each one no longer applies.

Implementation and downstream verification are separate evidence links. A checked plan does not establish downstream verification, so unverified closure stays visibly pending.

## Adoption Is Not Admission

`plan-input` prints adopted requirement references for later plan authoring. It creates no numbered plan.

Implementation still needs bounded feasibility, an exact write scope, completion witnesses, published plan bytes, and normal admission. A new report never authorizes implementation by itself.

## Commands

Use `.project-agent-workflow/scripts/development-direction.py example` to print a complete decision.

Use `check-decision` and `record-decision` for one decision, `render` (with `--check` for a read-only comparison) for the document, `plan-input` for adopted requirement references, and `inspect` for a readable local view.

Persisting a decision or the rendered document is a repository effect, so those commands run under the shared task worktree guard.
