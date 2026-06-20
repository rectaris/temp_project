# Japanese Technical Writing

This specification governs Japanese prose written in this repository itself.
The generated template version lives at `template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.

Sources:

- `https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d`
- `https://github.com/f4ah6o/tech-write-ja`
- `https://github.com/mizuamedesu/ReportSkills`

## Scope

Follow this file when writing or editing Japanese prose in repository documentation, plans, specifications, issue summaries, review comments, prompts, UI copy examples, or user-facing summaries.

This file is repository-local policy.
It does not require installing ReportSkills as an external skill.

The template file governs generated projects.
When a change affects the general Japanese-writing policy, update both this file and `template/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` unless the difference is intentional.

## Priority

- Follow explicit user instructions first.
- Follow required project structure, validation, Git, and template-maintenance rules before prose style.
- Use this file for Japanese wording choices after the technical content is correct.
- Use the project owner's product vocabulary when it conflicts with generic examples.

## Technical Writing Rules

- Write one sentence per line in Markdown prose.
- Separate paragraphs with a blank line.
- Treat each paragraph as one step in the argument.
- Put one topic in one paragraph.
- Make the first sentence identify what the paragraph is about.
- Keep definitions, classifications, and term roles consistent across sections.
- Match the strength of each claim to the evidence actually provided.
- Do not convert uncertainty into certainty unless the text already establishes the claim.
- Name the subject specifically instead of using broad words such as `AI`, `tool`, or `system` when the narrower subject is known.
- Avoid names, filenames, identifiers, timestamps, status codes, and metrics that are not needed later.
- State each claim once.
- Remove intermediate explanations that the target reader can infer.

## Formatting Rules

- Use code blocks for code, diffs, logs, configuration, and terminal output.
- Bold a term when first defining or introducing it.
- Do not use bold text as decoration.
- Use Japanese corner brackets for later mentions, aliases, and quoted expressions when they improve clarity.
- Do not use em dashes, horizontal bars, or double dashes in Japanese body text or headings for apposition or explanation.
- Do not use middle dots for ordinary Japanese parallel lists.
- Use a full-width colon for term definitions: `**用語**：説明`.

## ReportSkills Rules

Apply these ReportSkills-derived rules when writing Japanese reports, assignments, explanatory notes, or other prose where a plain human-written tone matters.

- Do not omit Japanese particles.
- Avoid parenthetical glosses that only restate a preceding term unless the parenthetical form is needed later.
- Do not use decorative bold emphasis in report prose.
- Prefer ordinary Japanese sentences over symbol-heavy lists or punctuation that makes the text look generated.
- Avoid hard-coded numbering in paragraphs and headings when the order may change during editing.
- Use Markdown list markers when list structure is needed.
- Do not use complex ASCII art for diagrams.
- Use Mermaid or another diagram format when a diagram is needed and the repository supports it.

## Empty Phrases

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
