---
name: graph-memory
description: Use when reading, proposing, reviewing, or writing durable graph memory. Requires project-local policy for graph connection, project identifier, schema, allowed operations, and write authorization.
---

# Graph Memory

Use this skill for durable graph memory, including Neo4j-backed memory, candidate memory review, Cypher generation, or memory writes.

## Policy Gate

1. Apply `.agents/skills/mcp-ops/SKILL.md` as the common external-service gate.
2. Use `external_services.graph_memory` and classify the exact graph operation as a read or write.
3. If the common gate denies the call, do not read or write graph memory. Use repository files, checked plans, validation output, and Git history.
4. Apply the graph-memory-specific rules below only after the common gate passes.

Do not assume a project identifier, node labels, relationship types, or property names. They must come from project-local policy or a linked graph-memory spec.

## Normal Read Rules

- Treat graph memory as auxiliary context, not the source of truth.
- Query only when durable prior context can affect the current task.
- Start from the configured project identifier or connection shape.
- Use limits on exploratory reads.
- Return compact fields such as labels, IDs, titles, summaries, statuses, and relationship types before full body fields.

## Write Boundary

- Require the common write-authorization check to pass for the exact project, node, relationship, property, and mutation.
- Prefer candidate-memory proposals from reviewed repository artifacts.
- Exclude secrets, credentials, private config, raw personal data, generated artifacts, build outputs, temporary logs, and speculative conclusions.
- Record important implementation decisions in repository files even when graph memory is updated.
- Do not write memory without explicit user intent or an approved project workflow.
