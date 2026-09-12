---
name: verify-copier-update
description: Verify whether one exact clean downstream Git baseline can adopt one exact trusted Copier template ref in a disposable clone. Use for downstream compatibility checks, not for applying or committing a live update.
---

# Verify Copier Update

`verify-copier-update`: A reusable Codex skill that checks one exact downstream Git baseline against one exact Copier template commit in an isolated workspace without changing the original downstream worktree.

Read [references/verification-contract.md](references/verification-contract.md) before running the bundled helper.

Use the downstream repository's `AGENTS.md`, routed Copier adoption policy, validation policy, and project command manifests to select at least one target-specific validation command.

Resolve the directory containing this `SKILL.md`, then run `scripts/verify-copier-update.py` from that directory with explicit target, source, source ref, unused output directory, template-task trust, and JSON argv validation inputs.

Inspect the verification manifest and command logs before reporting the result.

Run `scripts/triage-copier-update.py <manifest>` from the same directory to resolve the manifest's reason code into one owner and one next action, and report that resolution rather than a judgment of your own.

`verified`: All required isolated update, safety, downstream validation, and same-ref idempotence checks passed for the recorded target and source commit OIDs.

`rejected`: A completed update or required invariant check produced an observed incompatibility or safety failure.

`blocked`: A missing or unusable prerequisite prevented the required checks from completing, so compatibility remains unresolved.

`verification-manifest`: A local machine-readable record of one isolated verification run, including exact Git identities, command outcomes, changed-path classification, result, and unresolved runtime facts.

`update-triage`: The committed table in [references/update-triage.yaml](references/update-triage.yaml) that assigns every reason code the helper can emit one owner, one next action, and whether verifying again can change the answer.

An unclassified reason code exits non-zero and is reported upstream unresolved; do not infer an owner for it.

Do not use this Skill to change the original repositories, apply a live update, commit, push, install dependencies, access external services, accept force flags, or bypass a failed check.
