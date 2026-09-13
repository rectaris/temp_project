---
name: release-project
description: Prepare and publish a stable release of this Copier template repository. Use when asked to cut, tag, or publish a version of this repository, to continue a release whose outcome is uncertain, or to prepare release content without publishing. Do not use for adopting the template in a downstream project or for deploying an application.
---

# Release Project

`release-project`: The root-only runbook for releasing this template repository. It guides one requested release phase through existing repository policy, validation, and lifecycle commands. It is guidance, not an executor: every repository write and every external effect still goes through the normal commands and the normal authorization rules.

Read [references/workflow.md](references/workflow.md) before acting. Read it in full when the requested phase is publication, when a previous release attempt was interrupted, or when any observed state disagrees with what the runbook expects.

## Scope

Use this skill for:

- preparing release content in this repository (change log section, version anchors, release plan);
- publishing an authorized release (branch, pull request, tag, GitHub Release);
- inspecting an interrupted or uncertain release before retrying a write.

Do not use this skill for applying `copier update` in a generated project, for judging whether a downstream project should adopt a version, or for deploying any application. Downstream adoption is `verify-copier-update` and the downstream repository's own policy.

## Authority

Preparation and publication are separate phases. Completing preparation is never permission to publish.

Each external effect needs its own exact authorization: a branch push, a tag push, a pull request, and a GitHub Release are four separate effects. Apply `docs/agent/SPEC_EXTERNAL_SERVICES.md` to each one, and reuse an existing user authorization only when it already names that exact effect and target.

A checked release plan records what one past release did. It is evidence about history, not reusable permission and not proof that a later publication succeeded.

## Working Rules

Resolve the requested phase, the previous stable tag, the candidate commit, and the intended version from live repository state before proposing anything. Do not carry version, branch, or ref assumptions over from a past release plan.

Do the repository-changing part in a task-bound worktree through `scripts/manage-plan-worktrees.py`, and finish it with `publish` before any remote operation.

Let the existing checks decide version agreement. `scripts/check-copier-template.py` derives the released version from the newest dated `CHANGELOG.md` heading and refuses a disagreeing `README.md` pin, so it replaces any broad textual search-and-replace.

Bind every validation result to the exact commit it ran against. A passing pull-request head does not prove a merge commit or a tag commit.

Read `scripts/verify-downstream-baselines.py` results per baseline and per reason. A blocked result stops tagging; a `verified` result proves only the checks it actually recorded.

Stop and report rather than guessing whenever a tag already exists at a different target, a required check is unavailable, downstream verification is blocked, or post-tag CI fails. A published tag is never force-moved or deleted.

Report preparation commit, publication OID, tag target, CI outcome, downstream limitations, and Release URL or explicit non-publication as separate facts.
