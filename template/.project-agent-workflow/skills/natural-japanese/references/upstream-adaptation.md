# Upstream Adaptation

This skill is a project-controlled adaptation of:

- Repository: `https://github.com/coji/natural-japanese`
- Release: `v1.5.0`
- Commit: `21e632661a910bf97289c501089ad11eb8b4d85f`
- License: MIT

The upstream design contributed the separation between mechanical detection and contextual judgment, reader-and-purpose planning before drafting, natural Japanese rhythm checks, and the rule that findings require human or agent judgment.

This adaptation intentionally:

- keeps `.project-agent-workflow/docs/agent/SPEC_JAPANESE_TECH_WRITING.md` authoritative;
- uses three project-specific application depths instead of upstream command modes;
- removes runtime downloads, automatic upstream tracking, heavy semantic models, and required third-party packages;
- keeps only a bounded dependency-free advisory lint;
- protects facts, quotations, uncertainty, code, identifiers, project terms, requested form, and document purpose ahead of naturalness;
- prohibits fabricated experience, motive, emotion, or certainty;
- uses repository delegation policy for independent review instead of prescribing a fixed subagent workflow.

The bundled `LICENSE` preserves the upstream MIT notice.
Any future upstream update requires an explicit review of the new immutable commit, license, imported material, and local differences.
