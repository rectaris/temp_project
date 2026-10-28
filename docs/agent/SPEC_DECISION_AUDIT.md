# Decision Audit

Decision audit identifies important choices that are not explicit in the request, plan, or routed project docs.

It is analysis for deciding direction. It is not an implementation plan and must not be copied in full into `docs/plan/active`.

This repository root uses decision audit as documented policy and includes the generated repo-local `.codex/skills/decision-audit` skill for Codex skill discovery. `docs/agent/SPEC_DECISION_AUDIT.md` remains the normative root policy when the skill and this document differ.

## When To Run

Run a decision audit when the user explicitly asks for any of:

- `decision-audit`
- unstated important decisions
- missing decisions or unresolved issues
- multiple approaches with a recommendation
- recommendation reasons before implementation

Run a decision audit automatically before creating or materially updating an active plan when meaningful choices remain open in any of these areas:

- architecture or design boundaries
- storage, retention, or artifact location
- validation scope or acceptance gates
- lifecycle and ownership
- security, privacy, secrets, or access
- generated-file or template boundaries
- raw logs, summaries, compressed views, or evidence paths

## When To Skip

Skip decision audit when the task is small, mechanical, and already determined.

Examples:

- fix a typo
- run a named command
- apply a clearly specified single-file edit
- implement an active plan whose decisions are already complete
- answer a narrow factual question without changing repository artifacts

## Method

1. Read the user request.
2. Read the relevant active plan when one exists.
3. Read `docs/agent/spec-index.yaml` and the routed required specs.
4. List explicit requirements before inferred gaps.
5. Include only decisions that can change implementation, validation, lifecycle, storage, security, or artifact boundaries.
6. Compare viable approaches for each decision.
7. Recommend a direction when enough context exists.
8. Mark unresolved items clearly when user input or external facts are required.

Do not infer a decision only because more detail could exist. Include it only when choosing differently would materially change the work.

## Output Format

Use the user's language for the audit response. Japanese output is allowed when the user communicates in Japanese.

Use numbered decision items:

```text
1. Decision Item
   Explain why this matters.

   A: Approach description.
   B: Approach description.

   Recommended: A
   Reason: Explain the reason.
```

Use `Recommended: Needs user decision` when available context is insufficient.

## Implementation Preflight

The `decision-audit` skill carries one direct reference,
`references/implementation-preflight.md`, for the moment a task turns from
deciding into doing. It covers accepted-decision reuse, the requirement, scope,
condition, and witness preflight that runs before long plan prose, and exact
failure reproduction after a formal validation failure.

Read it in those situations and before broad integration when a tool or current-system assumption could invalidate the intended behavior.
Do not read it for an ordinary audit that changes nothing.

This document and the routed specifications stay normative. The reference
records how to apply them; it grants no new authority and never replaces
`docs/agent/SPEC_PLAN_WORKFLOW.md` or `docs/agent/SPEC_SECURITY.md`.

Reuse an accepted decision while the requirement, the accepted safety
conditions, the class of external effects, and the approving authority are all
unchanged. A new plan id, a routine checkpoint, or a resumed session does not by
itself require the same approval again. A changed requirement, a changed safety
condition, expanded external effects, or continuing a stopped run always does.

### Optional scope diagnostics

When the installed command supports `--scope-candidates`, explicitly request it
with the existing check command, not the write command:

```sh
python3 scripts/create-root-plan.py check --input authoring-input.json --scope-candidates
```

The option adds advisory `scope-candidate` rows from fixed registration sources.
They identify possible counterparts, ownership coverage and delivery registrations;
missing, unsafe, dynamic or unsupported correspondence stays unknown.
A suggested path grants no write permission and requires no automatic edit.
Catalog projections report declared path/digest references without opening their
referenced policy assets or proving that their digests agree.

For normalized `.py` paths already declared in `write_scope`, the same option emits
`python-source-observation` records with available SHA-256, UTF-8 byte size,
physical CR/LF/CRLF line count, AST declaration/import positions and aliases.
Definition spans start at the declaration, not necessarily its decorators.
Potential loader-call spellings omit arguments and bodies and do not prove callable
identity or exhaustive dynamic-load detection.
Source reads are descriptor-relative, no-follow, single-link regular-file reads
with bounded size and before/after/live identity checks.
The Python observation budget is 2 MiB per file, not a source acceptance limit.
Unavailable source retains unknown measurements; parser failure retains available
source facts but leaves syntax results null rather than proven empty.
Syntax detail also has representation budgets: 1024 records per file, 4096 across
sorted declared paths, and 128 KiB per serialized observation. Definitions,
imports, each imported alias and potential loader calls consume records.
Budget exhaustion retains available source measurements but makes syntax and
dependent sets unknown/null, never a silently truncated or proven-empty result.
These are diagnostic budgets, not source acceptance limits or a file-splitting rule.
Diagnostic JSON uses ASCII escapes so admitted Unicode path characters cannot
split records; those separators are also escaped in the diagnostic check's human
report so they cannot inject additional record-prefixed lines.

One `python-relative-import-relations` aggregate derives only from those captured
observations, without reading inferred modules, initializers or directories.
A lexical relative module reference becomes a relation only when exactly one
explicitly declared parseable module or package spelling matches.
Missing, ambiguous, absolute, dynamic and attribute-versus-submodule resolution
stays unknown; execution contexts and imported attribute identities stay unknown.
`cycles` groups self-loops and cyclic strongly connected components in this
observed static subgraph, not executed cycles or whole-project acyclicity.
`reverse_dependents` lists other declared parsed sources reaching each target,
with distinct sorted direct/transitive path-digest endpoints and no self entry.
Unknown targets retain null sets; empty parsed sets mean no observed consumer,
not proof that runtime consumers are absent.

Choose the analyzer code and Python runtime independently of untrusted inspected
data. The diagnostic refuses a declared Python file overlapping the selected
helper, entrypoint or known loaded module by path or file identity. Before
metadata/YAML observation, the isolated child also refuses declared Python
paths inside its actual stdlib/platstdlib/purelib/platlib directories, including
packages it could import later. These refusals make no non-execution claim for
an overlapping runtime. To inspect those same files,
invoke the Python check CLI from a separately accepted analyzer/runtime and pass
the inspected project with the existing `--root` option.
This is a runtime/data role boundary, not a filename exclusion: an external
accepted analyzer still observes the declared tool files as data.
It cannot make an untrusted bootstrap safe after that bootstrap has already run;
never start candidate tool code to authorize or inspect itself.

The CLI runs the helper in an isolated, non-bytecode Python child with a minimal
environment. The child excludes ordinary cwd/script-directory dependency-name
lookup for observation. YAML correspondence uses PyYAML only when that isolated
interpreter can import it; otherwise correspondence remains unknown.
This is not an OS sandbox or proof of complete interpreter/native/package closure.
The parent incrementally consumes at most 8 MiB of combined stdout/stderr, with
stderr additionally capped at 64 KiB. The existing child deadline is 30 seconds;
exceeding time or output bounds terminates the child process group and refuses
the requested diagnostic without partial success.
Closed streams and a successful leader exit do not establish an empty process
group. The parent observes non-reaping leader completion during pipe consumption,
not only after EOF. It terminates residual group members while that leader
identity is still held, drains buffered output, then reaps and preserves the
leader's original exit status. An inherited open pipe does not turn success into
a deadline failure.
Before starting the diagnostic helper, a trusted immediate-exit child proves
current `waitid`/`WNOWAIT` operation: its unchanged exit is observed twice without
reaping, then explicitly reaped. Symbol availability and Python's default
`SIGCHLD` metadata alone are insufficient; auto-reaping configurations such as
`SA_NOCLDWAIT` refuse before the helper starts. The probe shares the same deadline.
The caller must retain exclusive child-reaping ownership during the operation.
If helper observation loses that ownership, the diagnostic refuses and does not
signal an unverified numeric process-group identity. No unsafe reap-then-kill
fallback or complete runtime/OS-sandbox guarantee is introduced.
The helper also bounds its complete serialized response to 8 MiB.
A launch or diagnostic failure never falls back to in-process source loading.
Ordinary checks, structural refusals, existing write behavior and Python
`--print-digest` output remain unchanged; digest-only checks suppress diagnostics.
The generated shell accepts the option only with `--check`.
No row proves complete runtime dependencies, forbidden-import policy, responsibility
separation, semantic sufficiency, efficiency, execution or acceptance authority.

### Evidence For Implementation Assumptions

Connect each design-critical assumption to the existing processing, its owners and consumers, the adopted tool version, and the intended end-to-end behavior.
Distinguish documented claims from observed behavior and keep missing evidence explicit.
When material uncertainty remains, use bounded normal and assumption-breaking probes before broad integration, within existing read, write and execution authority.
A version string, zero exit status or aggregate check count alone does not establish the required behavior.
Skip extra investigation for mechanical work and reuse applicable accepted evidence rather than repeat it without a changed premise.

If code violates a settled design, use the existing bounded implementation correction path.
If evidence invalidates a design assumption, return to decision audit before another patch; do not keep patching around a premise the evidence refuted.
This distinction grants no continuation: formal validation failure retains diagnosis_required, and exhausted budgets and stopped runs retain their existing owner-authorization rules.
Use the existing template-feedback guidance for a reusable lesson, not as authority to repair or publish it.

## Artifact Boundary

Full decision-audit output belongs in one of:

- chat
- raw agent logs
- handoff research artifacts
- dedicated decision artifacts
- `.agent-artifacts/decision-audits/`

Full decision-audit output does not belong in `docs/plan/active`.

After the direction is accepted, write only final decisions into the active plan. Do not preserve approach matrices, debate transcripts, or long recommendation rationale in active plans.

## Active Plan Conversion

When audit outcomes affect an active plan:

1. Keep the plan written as executable agent instructions.
2. Add only final decisions to the `## Decisions` section.
3. Convert recommendations into direct instructions when accepted.
4. Link or reference a durable audit artifact only when later agents need the full analysis.
5. Do not require later agents to read the full audit unless it contains necessary evidence not captured by final decisions.
