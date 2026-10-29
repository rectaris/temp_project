# Decision Audit

Decision audit identifies important choices that are not explicit in the request, plan, or routed project docs.

It is analysis for deciding direction. It is not an implementation plan and must not be copied in full into `docs/plan/active`.

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
3. Read `.project-agent-workflow/docs/agent/spec-index.yaml` and the routed required specs.
4. List explicit requirements before inferred gaps.
5. Include only decisions that can change implementation, validation, lifecycle, storage, security, or artifact boundaries.
6. Compare viable approaches for each decision.
7. Recommend a direction when enough context exists.
8. Mark unresolved items clearly when user input or external facts are required.

Do not infer a decision only because more detail could exist. Include it only when choosing differently would materially change the work.

## Output Format

Use the user's language for the audit response. English labels are acceptable in reusable prompts, but Japanese output is allowed when the user communicates in Japanese.

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
`.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` or `.project-agent-workflow/docs/agent/SPEC_SECURITY.md`.

Reuse an accepted decision while the requirement, the accepted safety
conditions, the class of external effects, and the approving authority are all
unchanged. A new plan id, a routine checkpoint, or a resumed session does not by
itself require the same approval again. A changed requirement, a changed safety
condition, expanded external effects, or continuing a stopped run always does.

### Optional scope diagnostics

When the installed command supports `--scope-candidates`, explicitly request it
with the existing check command, not the write command:

```sh
.project-agent-workflow/scripts/create-plan.sh --check --input authoring-input.json --scope-candidates
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
data. The diagnostic refuses a declared file overlapping the selected helper,
entrypoint, interpreter executable or known module source/cache by path or file
identity, regardless of its suffix. Stored module namespace metadata is read
without invoking deferred module attribute hooks. Before metadata/YAML
observation, the isolated child also refuses declared paths inside its actual
stdlib/platstdlib/purelib/platlib directories, including later dependencies.
The shared renderer applies the same known-role refusal before opening declared
sources, using the built-in stored module namespace rather than subclass attributes.
Stored runtime paths accept exact built-in strings and bytes; bytes use the
filesystem codec. Other non-null representations refuse without custom coercion.
An import-blocking `None` entry in `sys.modules` is not a runtime module and is skipped.
These refusals make no non-execution claim for an overlapping runtime. To inspect
those same files,
invoke the Python check CLI from a separately accepted analyzer/runtime and pass
the inspected project with the existing `--root` option.
This is a runtime/data role boundary, not a filename exclusion: an external
accepted analyzer still observes the declared tool files as data.
For the command child, `-I -S -B` suppresses automatic site startup.
Using only built-in modules, the existing identity guard activates before its
file-backed dependency imports; site initialization then retains access to
optional runtime dependencies.
The existing JSON request must match the checked root/path list supplied for
this early protection.
Rendering restores the previous guard state, so the bootstrap-active child
retains protection for subsequent ordinary exit callbacks; directly loaded
renderers retain their own pre-call state.
This cannot make an untrusted Python startup or helper safe after it has run;
never start candidate tool code to authorize or inspect itself.

During rendering, including direct calls to the shared renderer, a process-local
Python audit guard compares attempted runtime opens, Python execution and native
extension imports with the physical identities of explicitly declared data.
Runtime-side symlinks and source-less bytecode aliases cannot bypass this check.
Each loaded helper instance uses one lock to refuse its own concurrent or nested
renders. Separately loaded instances have separate guards; their process audit
hooks can impose additional conservative refusals. This is not a whole-process
serialization or cross-instance-success guarantee.
The descriptor-based reader grants a thread-local, single-use exception only to
the exact path and flags of each open used for descriptor acquisition. Decode,
hash computation, unrelated threads, imports and execution inherit no exception.
Declared identity changes refuse the attempted runtime access rather than imply
that unavailable data is empty.
A rejected optional PyYAML import leaves its correspondence unknown.
The independently selected bootstrap and runtime image must remain trusted and
stable; these metadata checks are not a complete dependency-closure or filesystem
race-isolation proof.

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
Before command-side Git discovery or plan-ID reservation, the optional diagnostic
proves current child observation on a fixed immediate-exit Python probe.
It requires Linux native `pidfd_spawn`, `pidfd_open`, `pidfd_send_signal`, actual
`waitid(P_PIDFD)` and `waitid(P_PID)`, own-session creation and verified `killpg`
support. Unavailable capability refuses only this diagnostic, not ordinary
authoring or digest-only checks.
GNU libc `pidfd_spawn` returns an owned process descriptor atomically with creation,
so neither PID reuse nor failure to allocate a later handle grants signal authority.
Before any child is created, descriptor signal0 is exercised against the caller.
The fixed probe creates its own session and exits zero. That unchanged exit is
observed twice with `WNOWAIT` and through the helper's `P_PID` observation form.
The exact descriptor `SIGKILL` permission is exercised against the already exited,
still-unreaped probe. Its PGID and SID must both equal that held original PID
before the helper's exact `killpg(SIGKILL)` interface is exercised on the verified
probe group. Only then is the unchanged exit explicitly reaped through its FD.
These calls test current invocation and permission, not causal termination of an
already exited probe or arbitrary state-sensitive or future policy stability.
Symbol availability and Python's default `SIGCHLD` metadata alone are insufficient:
auto-reaping configurations such as `SA_NOCLDWAIT` refuse before Git reservation or
helper launch, including when the Python signal metadata still reports default.
The probe reserves bounded cleanup time within the same 30-second deadline passed
to the helper. A stopped probe is terminated and reaped through its process FD;
the group-signal test requires its separate held session/group certificate.
No blocking `waitpid`, raw clone or unverified numeric PID signalling is used.
The helper likewise reserves cleanup time within that deadline. Final leader
observation remains nonblocking; only an observed exit is reaped, with a
zero-timeout wait rather than an unconditional blocking wait.
The caller must retain exclusive child-reaping ownership during the operation.
If helper observation loses that ownership, the diagnostic closes its own pipes
and refuses without an unbounded wait or signalling an unverified numeric group
identity. A refusal with unconfirmed cleanup does not prove no member remains.
No unsafe reap-then-kill fallback is introduced.
The helper also bounds its complete serialized response to 8 MiB.
A launch or diagnostic failure never falls back to in-process source loading.
Ordinary check results, structural refusals, existing write behavior and Python
`--print-digest` output remain unchanged; digest-only checks suppress diagnostics.
Entry-point checks must not depend on a caller-supplied `-B` or inherited bytecode
suppression to keep command-directory bytes, including ignored caches, unchanged.
The root adapter suppresses caching before local tooling imports; the generated
shell invokes the option only with `--check` and disables bytecode there.
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
