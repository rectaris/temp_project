# Project Agent Workflow Core

This directory is the Copier-managed workflow core.

Update files here through `copier update` and do not add project-specific policy or runtime facts here.

Project-owned policy belongs under `docs/agent/`, and project-owned plan state belongs under `docs/plan/`.

Host-discovered files under `.agents/`, `.codex/`, and `.github/` are narrow projections or integrations whose managed status is declared in `ownership.yaml`.

Root entrypoints and project state are seeded once and are not overwritten by later Copier updates.
