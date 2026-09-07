# Project-Controlled Japanese Workflow

## Conflict Order

Apply requirements in this order:

1. User-requested tone, form, and output constraints.
2. Facts, quotations, uncertainty, identifiers, numbers, operators, code blocks, and project terminology.
3. Document purpose and required structure.
4. `.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.
5. This skill's naturalness advice.
6. Mechanical lint scores and findings.

Never change a higher-priority item to satisfy a lower-priority item.
A smoother sentence is a regression when it changes meaning, confidence, attribution, requested structure, or a project term.

## Short Reply

Use this depth for ordinary Japanese chat replies and brief status messages.

- Do not run a subprocess.
- Put the concrete outcome first.
- Remove empty posture, repeated conclusions, and unexplained broad labels.
- Preserve the user's tone and every factual qualification.
- Stop after one final read.

## Japanese File Work

Use this depth when drafting or revising a Japanese Markdown or text file.

1. Identify the reader, purpose, requested form, and required headings.
2. Mark quotations, code blocks, identifiers, numbers, project terms, facts, and uncertainty as protected.
3. Draft or revise for one topic per paragraph, explicit subjects, natural particles, and readable sentence boundaries.
4. Run the bundled lint at most once per draft unless the user requests another pass.
5. Review each finding in context. Revise only when the change preserves all protected content and document purpose.
6. Read the finished file once without using the lint score as a quality target.

The lint is dependency-free, offline, diagnostic, and non-corrective.
It deliberately skips fenced code blocks and reports suggestions with exit status zero.
Input and execution errors return a nonzero status.

## Important Long-Form Prose

Use this depth for externally visible, high-impact, or long Japanese documents.

- Complete the file-work depth first.
- Review whether headings fit the document type. Technical specifications and references usually need subject or question headings; decision documents may benefit from conclusion headings.
- Read headings and paragraph openings as a structure-only outline.
- Check that terms remain stable and that explanations match the reader's knowledge.
- Inspect reading load caused by long dependencies, buried lists, repeated sentence shapes, and uniform paragraph length.
- Obtain an independent reader review when repository delegation policy permits it. The main session owns every edit and acceptance decision.

Do not split authorship of one document merely to create an independent review.

## Protected Content

Do not alter these merely to sound natural:

- direct quotations or attributed wording;
- facts, dates, counts, identifiers, commands, operators, and code;
- uncertainty, hypotheses, disputed points, and confidence levels;
- project terminology and defined labels;
- required sections, formats, or document purpose;
- a personal voice supplied by the user or source.

Never invent experience, motive, emotion, preference, or certainty.
If naturalness conflicts with protected content, retain the protected content and explain any remaining awkwardness only when it affects the requested result.

## Non-Use Boundary

Do not invoke this workflow for:

- code-only changes;
- JSON, YAML, TOML, CSV, or other machine-readable data whose prose is incidental;
- quoted or legal text that must remain exact;
- generated output that the task does not ask to edit;
- a request whose only Japanese content is a filename, identifier, or command.
