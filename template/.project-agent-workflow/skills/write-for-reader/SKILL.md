---
name: write-for-reader
description: Draft and review concrete user-facing progress updates, proposals, explanations, blocking reports, and final summaries without relying on unstated knowledge or undefined terms. Use for every substantive message that reports work, recommends a change, explains technical behavior, asks the user to decide, or claims completion.
---

# Write for Reader

write-for-reader is the Codex skill that drafts and reviews user-facing progress updates, proposals, explanations, and final summaries against the repository's user-communication specification.

1. Read `.project-agent-workflow/docs/agent/SPEC_USER_COMMUNICATION.md` directly.
2. Extract the facts already shared with the reader, the repository evidence needed for the answer, the concrete effect on the reader, and any remaining unknowns.
3. Use `define-referents-first` before introducing a new or compressed label when one label could hide multiple concrete referents.
4. Draft the applicable message type defined by the specification without adding empty sections.
5. Put the reader-relevant outcome first, then include only the detail needed to understand, verify, decide, or continue.
6. Review every substantive user-facing message against the specification before submitting it.

For Japanese text, also follow `.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.

Do not use this skill as a substitute for validation evidence or the stricter referent contract required by `SPEC_REFERENT_FIRST.md`.
