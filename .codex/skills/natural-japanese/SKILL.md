---
name: natural-japanese
description: Apply project-controlled Japanese naturalness guidance to short replies, Japanese file drafting or revision, and important long-form review. Use only after project policy and preserve facts, quotations, uncertainty, requested form, document purpose, code, and project terminology.
---

# Natural Japanese

Use this skill as an optional review layer after `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`.

1. Classify the task as a short reply, file work, or important long-form prose.
2. Read `references/workflow.md` and apply only that depth.
3. Preserve every protected fact and structural requirement before changing wording.
4. For file work, run `python3 .codex/skills/natural-japanese/scripts/check-japanese-prose.py --json <file>` at most once per draft unless the user asks for another pass.
5. Treat every finding as advisory and decide from context whether to revise or retain the text.
6. Read `references/upstream-adaptation.md` before changing this skill or importing more upstream material.

Do not use this skill for code-only edits, machine-readable data, byte-exact text, or as a reason to fabricate personal experience, motive, emotion, or certainty.
