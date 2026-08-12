---
name: browser-ops
description: Route JavaScript-rendered page inspection, browser-produced artifacts, DOM inspection, and browser interaction through an authorized browser backend. Use when a plain URL lookup is insufficient.
---

# Browser Operations

Before provider access, read `references/browser-run-policy.md`, `.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md`, and `docs/agent/external-services.yaml`.

Classify the request as a browser read or write, apply the external-service gate, then select the compatible authorized backend. Do not use this skill for ordinary HTTP retrieval. For a write, require the exact configured authorization rule and current user authorization for the exact remote effect.
