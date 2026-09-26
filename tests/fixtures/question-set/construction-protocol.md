# Plan-record question set construction protocol

This protocol fixes how `scripts/build-plan-question-set.py` turns committed
plan records into labeled questions for one decision point: the
`implementation_risk` classification that routes the writable runner.

The command is root-only and offline. It reads committed plan files and Git
history, calls no provider, needs no network, and writes no file. The report is
printed to stdout. Save a durable copy under `.agent-artifacts/`, outside the
repository index.

## Label

- The label is the `implementation_risk` value the author declared when the plan
  was first committed. It records the author's judgment at authoring time, not
  an observed outcome. Predicting an outcome from `status` is a separate
  question set and is out of scope.
- Admitted values are `low`, `ordinary`, and `high`. Any other value, including
  `medium` and a differently capitalized value, is excluded with its raw value
  and is never coerced. A missing value and a repeated field are excluded too.

## Question construction

- Enumerate every `docs/plan/**/NNN-*.md` file at the scanned revision, at most
  4096 files. A file name found in two lifecycle locations is excluded.
- Read each plan from the first commit, in reverse topological order over the
  full history, that added a file with that exact name anywhere under
  `docs/plan/`. A move between lifecycle directories keeps the name, so the
  source is the authored file rather than its archive. A plan rewritten under a
  new name is authored again at that name.
- An addition that does not descend from that first commit is concurrent, such
  as a squash of the same file on a release branch. The earliest committed of
  the concurrent additions is the source. When several share that earliest
  commit time with different bytes, the plan is excluded as ambiguous.
- Exclude a source that exceeds 256 KiB or is not UTF-8.
- Exclude a source first committed with a `status` other than `backlog`,
  `deferred`, `in_progress`, or `active`, or with a completed task checkbox. Its
  bytes were recorded after execution started.
- The question input is the source text with the leading manifest fields
  `status`, `successor_plans`, `replan_contract`, `replan_sources`,
  `replan_source`, `human_approval_status`, and `implementation_risk` removed,
  together with their list items. Every other byte is kept, so the same input
  can be the state of a later scoring call.
- After removal, a source whose input still contains `status` followed by a
  colon, or any other removed field name as a whole token, anywhere including
  body prose, is excluded. `status` alone is an ordinary word, so only its
  field form counts. The command never emits such an input.
- Each question records its plan file, current path, source path, source
  commit, source commit time, label, lineage group, partition, the input, and
  the input's SHA-256 digest.

Every excluded plan is listed with its source path, source commit, raw label,
and every reason, and the report states the total exclusion count and the count
per reason.

## Partitions

- Authoring time is the committer timestamp of the source commit.
- Plans linked by `successor_plans`, `replan_sources`, or `replan_source`, or
  sharing one `replan_contract`, as recorded at the scanned revision, form one
  lineage group. A successor and its source share wording, so a group is never
  split.
- A group whose earliest emitted question was committed at or after
  `2026-09-14T00:00:00Z` is held out. Every other group is used for tuning. The
  report counts tuning questions committed after the cutoff, because a group
  that began earlier keeps its later members on the tuning side.
- Adding members or merging groups only moves a question from the holdout into
  tuning. Removing a group's earliest question from the scanned tree, or
  excluding it, can move later members into the holdout, so read a saved
  report against the revision it records and check it with `verify`.
- The cutoff is frozen here. Changing it is a protocol change and invalidates
  every earlier holdout result.

## Statistics

- The report states per-class counts and the majority-class share for all
  emitted questions and separately for each partition.
- The declared minimum is 10 questions per class. A class below it is reported
  as not measurable and receives no share. The tuning partition's counts tell a
  later weight fitting, before it starts, whether each class has enough records
  to fit on.

## Committed cases

`tests/fixtures/question-set/cases.json` holds a few tuning questions
regenerated from this repository's history, each marked `used_for_tuning`.
`tests/validation_tools/question_set.py` checks that the command still derives
the same source commit, source path, label, input digest, and partition for
them. The file holds no holdout question, holdout label, or partition list.

## Holdout handling

- Keep the held-out partition unused until the dimensions and weights fitted on
  the tuning partition are frozen.
- A holdout result used to retune those weights invalidates the evaluation, and
  the retuned run must record the holdout as `used_for_tuning`.
- `verify` regenerates a saved report from committed history and names every
  question that no longer matches. A match proves that the saved questions are
  derived from the recorded commits; it does not prove that the holdout stayed
  unseen.

## What the question set does not mean

The question set measures agreement with declared labels only. A declared label
is not ground truth about how hard the work was, and the classes are
imbalanced. Every score computed from it must be read beside the majority-class
share of the same records.
