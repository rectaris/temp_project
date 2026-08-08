# User Communication

This specification governs substantive messages that coding agents write for users of this repository.

It covers progress updates, proposals, explanations, review summaries, completion reports, and statements that ask the user to decide or act.

`SPEC_JAPANESE_TECH_WRITING.md` owns Japanese sentence style and formatting.

`SPEC_REFERENT_FIRST.md` owns the stricter workflow for introducing a new or compressed label that could hide multiple concrete referents.

## Reader Knowledge Boundary

Assume that the reader knows only facts supplied in the conversation, established project vocabulary, and facts explained in the current message.

Do not rely on an implementation detail merely because the agent discovered it while reading the repository.

When a repository fact affects the conclusion, explain its relevant behavior or effect instead of giving only a filename, identifier, or internal label.

Distinguish confirmed facts, inferences, hypotheses, and unknowns.

Do not turn an unverified assumption into a completed or certain claim.

## Terms

Describe the concrete target, behavior, condition, or event before assigning a new label.

Introduce a label only when later references need it.

Define a necessary new label or abbreviation at first use in ordinary language.

Use the concrete description instead when a stable one-sentence definition is not available.

Do not make the reader infer what broad words such as `system`, `handling`, `optimization`, `support`, or `cleanup` denote when a narrower subject is known.

## Message Content

Lead with the outcome or decision that matters to the reader.

For a progress or completion report, include the changed target, the behavior before and after the change, validation evidence, and remaining uncertainty when each item applies.

For a proposal, include the observed problem, the proposed change, the reason it should address the problem, material disadvantages or risks, and any unresolved decision when each item applies.

For an explanation, connect each technical detail to the question it answers or the effect it causes.

For a blocking report, state the attempted outcome, the exact blocking condition, the evidence for that condition, and the user input or external change needed to continue.

Do not report only that work was organized, improved, supported, handled, optimized, or completed.

Do not add headings or fields that contain no useful information.

Keep short answers short when the concrete outcome is already clear.

## Evidence And References

Match the strength of each claim to the available evidence.

State the validation command and result when validation supports completion.

Explain a cited file or symbol's relevance instead of making the reference carry the explanation.

Include identifiers, paths, metrics, and timestamps only when the reader needs them to verify, locate, or act on the result.

Do not describe a planned action as if it already occurred.

## Final Review

Before submitting a substantive message, review it from the reader's stated knowledge boundary.

Remove unexplained labels, hidden assumptions, abstract completion claims, unsupported certainty, and implementation details that do not help the reader decide or verify.

Preserve correct uncertainty rather than filling gaps with plausible detail.

The review may keep an already compliant message unchanged.

## Enforcement Boundary

`AGENTS.md` makes this specification part of the repository instructions.

The `write-for-reader` skill supplies the operational drafting workflow without redefining this policy.

Apply this review through repository instructions and the operational skill before submitting the message.

The Stop hook must not infer missing communication review from message length, selected words, bullet count, or another property of the proposed text.

When Codex hooks are enabled, Stop blocking is reserved for deterministic repository lifecycle failures.

Deterministic validation checks policy routing, Skill parity, Hook wiring, and fixed evaluation scenarios.

Independent reader or agent evaluation remains necessary for empirical semantic quality.
