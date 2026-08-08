# Japanese Technical Writing

This generated specification adapts the Japanese technical-writing standards published by k16shikano, packaged for reuse by f4ah6o, and supplemented with ReportSkills report-prose rules.
Use it as repository-local agent policy, not as an installed skill.

Sources:

- `https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d`
- `https://github.com/f4ah6o/tech-write-ja`
- `https://github.com/mizuamedesu/ReportSkills`

## Scope

Follow this file when writing or editing Japanese prose in documentation, plans, specifications, issue summaries, review comments, prompts, or UI copy.
Use the project owner's product vocabulary when it conflicts with generic examples here.

This file governs prose quality.
It does not replace validation, Git, security, UI, or domain-specific specs.

## Formatting

- Write one sentence per line in Markdown prose.
- Separate paragraphs with a blank line.
- Use code blocks for code, diffs, logs, configuration, and terminal output.
- Move side notes, naming background, and source notes into footnotes when they interrupt the main argument.
- Bold a term when first defining or introducing it.
- Use Japanese corner brackets for later mentions, aliases, and quoted expressions.
- Do not use em dashes, horizontal bars, or double dashes in Japanese body text or headings for apposition or explanation.
- Do not use middle dots for ordinary Japanese parallel lists.
- Use a full-width colon for term definitions: `**用語**：説明`.

## Report-Style Naturalness

Apply these additional rules when writing Japanese reports, assignments, explanatory notes, or other prose where a plain human-written tone matters.

- Do not omit Japanese particles.
- Avoid parenthetical glosses that only restate a preceding term, such as `commonization (abstraction)` or `virtual file system (VFS)`, unless the parenthetical form is needed later.
- Do not use decorative bold emphasis in report prose.
- Prefer ordinary Japanese sentences over symbol-heavy lists or punctuation that makes the text look generated.
- Avoid hard-coded numbering in paragraphs and headings when the order may change during editing.
- Use Markdown list markers when list structure is needed.
- Do not use complex ASCII art for diagrams.
- Use Mermaid or another diagram format when a diagram is needed and the repository supports it.

## Paragraphs And Argument Flow

- Treat each paragraph as one step in the argument.
- Put one topic in one paragraph.
- Make the first sentence identify what the paragraph is about.
- Show the logical relation to the previous paragraph at the start when the relation could be missed.
- Resolve doubts, objections, and limitations before placing the final conclusion.
- Do not state a conclusion, handle objections, and then restate the same conclusion.
- When denying a claim, write the denied claim precisely and give the reason for denial.
- Put forward references such as later sections only after the current argument has reached a stable point.

## Argument Rigor

- Do not convert uncertainty into certainty unless the text already establishes the claim.
- Keep uncertainty when describing unverified facts, reader doubts, log-based inference, a person's perception, or counterfactuals.
- Do not group distinct decisions, causes, or problems under one vague label.
- Do not reduce multi-cause events to a single cause.
- Keep definitions, classifications, and term roles consistent across sections.
- When asserting causality, include the mechanism in one concrete sentence.
- Do not imply that detection, prevention, guarantee, or resolution always works.
- Match the strength of each claim to the evidence actually provided.
- Define the central term of a section before relying on it.
- If a section sends an unresolved point forward, confirm that the later section actually handles it.

## Reader Load

- Avoid names, filenames, identifiers, timestamps, status codes, and metrics that are not needed later.
- Clarify abstract expressions in place when the reference is not obvious from context.
- Before adding another example, explain how it differs from the previous example and why it is needed.
- Keep concrete details that support the section's question or conclusion.
- Omit decorative precision that does not change the reader's judgment.
- Do not make readers remember a term before it has a role in the argument.

## Viewpoint And Diction

- Prefer actors and actions over passive result lists.
- Do not add fictional personas unless the task needs a concrete scenario.
- Avoid addressing the reader as `あなた` inside the argument; use roles such as `読者`, `開発者`, or `利用者`.
- Name the subject specifically instead of using broad words such as `AI`, `ツール`, or `仕組み` when the narrower subject is known.
- After introducing a technical term, keep using that term instead of drifting back to vague labels.
- Use conventional terminology for the field.
- Do not borrow technical-sounding words for nontechnical relations.

## Restraint

- Use rhetorical questions, suspense, and short emphatic paragraphs only where they change the effect of the argument.
- Do not use bold text as decoration.
- Avoid dramatic turns, slogan-like contrasts, and danger lists when a factual sentence is enough.
- Do not announce importance with empty openings such as `重要なのは`.
- Prefer ordinary verbs over strained metaphors.
- Write prohibitions as practical judgment when that fits the context.

## LLM-Like Empty Phrases

Avoid phrases that add posture without adding content.
Examples include:

- `重要なのは`
- `ここでは見ていく`
- `正面から扱う`
- `多角的に分析する`
- `包括的に`
- `深掘りする`
- `言語化する`
- `〜の観点から`
- repeated `さらに`, `また`, and `加えて`
- `非常に`, `極めて`, and `大いに` when they only intensify

Use these expressions only when they carry specific information in the sentence.

## Redundancy

- State each claim once.
- Merge adjacent sections when they play the same role.
- Do not summarize a scene immediately after describing it unless the summary changes the argument.
- Combine parallel facts with the same logical role into one sentence.
- Remove intermediate explanations that the target reader can infer.
- Do not stage imaginary exchanges with the reader as a substitute for direct argument.
- Do not introduce concepts or document names before the text needs them.
- Keep rhythm-building connectors when they improve readability and do not duplicate meaning.

## Headings

- Make headings identify the subject or question handled by the section.
- Do not use headings that only name a work step, such as returning to an example.
- Do not make a heading reveal the conclusion as a slogan.
- Use either a question or a noun phrase, whichever fits the surrounding tone.

## Reader Honesty

- Do not hide when an example could look artificial.
- Acknowledge plausible reader doubts and give a short reason the example can occur in practice.
- Do not write unverified facts as if they were confirmed.
