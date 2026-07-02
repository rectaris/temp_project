# Skill Authoring

This specification defines how agents create or update Codex skills in this template development repository.

Use the system `skill-creator` skill when it is available.
When it is unavailable, follow this file directly.

## Scope

Follow this file when adding, updating, vendoring, or reviewing:

- root `.codex/skills/<skill-name>/` skills;
- generated `template/.codex/skills/<skill-name>/` skills;
- skill `SKILL.md` files;
- skill `agents/openai.yaml` metadata;
- skill bundled `references/`, `scripts/`, or `assets/`.

## Placement

- Put reusable generated-project skills under `template/.codex/skills/<skill-name>/`.
- Put root-only workflow skills under `.codex/skills/<skill-name>/` only when the root repository itself needs them.
- Keep project-specific facts out of generic template skills.
- Put project-specific values, service identifiers, schemas, credentials policy, and domain rules in generated project `docs/agent/` specs or project-owned files.
- Do not put skill authoring rules only in README files.

## Skill Shape

Each skill directory must contain:

- `SKILL.md`;
- `agents/openai.yaml` unless there is a documented reason to omit UI metadata.

Optional resources:

- `references/` for detailed guidance loaded only when needed;
- `scripts/` for deterministic repeatable operations;
- `assets/` for templates, images, fixtures, or other output resources.

Do not add auxiliary files such as `README.md`, `CHANGELOG.md`, or `QUICK_REFERENCE.md` inside skill folders unless a consumer explicitly requires them.

## Naming

- Use lowercase letters, digits, and hyphens only.
- Keep names short and action-oriented.
- Namespace by tool or service when it improves trigger clarity.
- Make the folder name match the `name` field in `SKILL.md`.

## `SKILL.md`

- Keep `SKILL.md` concise.
- Use YAML frontmatter with only `name` and `description`.
- Make `description` state both what the skill does and when agents should use it.
- Put trigger conditions in `description`, not only in the body.
- Write the body as direct operational guidance.
- Move detailed examples, schemas, matrices, and long procedures into `references/`.
- Link each reference from `SKILL.md` and state when to read it.
- Avoid deeply nested references; prefer one reference layer from `SKILL.md`.

## `agents/openai.yaml`

- Keep UI metadata consistent with `SKILL.md`.
- Include a human-facing display name, short description, and default prompt.
- Regenerate or update this file when the skill purpose, trigger conditions, or primary workflow changes.
- Do not add brand colors, icons, or optional UI fields unless they are intentionally provided.

## Bundled Resources

- Add scripts only when deterministic behavior or repeated use justifies them.
- Test added scripts by running them or a representative sample.
- Put large procedural detail in `references/`, not in `SKILL.md`.
- Put files meant for generated output in `assets/`, not `references/`.
- Remove placeholder resource files before completion.

## Workflow

1. Identify concrete tasks that should trigger the skill.
2. Decide whether a skill is warranted, or whether a project spec, script, or README update is enough.
3. Choose root-only or generated-template placement.
4. Create or update the skill folder.
5. Keep `SKILL.md` lean and move detailed guidance into direct references.
6. Update `agents/openai.yaml`.
7. Update routing, validation, and smoke coverage when the skill becomes part of the reusable template.
8. Validate before completion.

## Validation

For root or template skill changes:

- run `python3 scripts/validate-changes.py --all`;
- run `scripts/lint-project-workflow.sh`;
- run `tests/smoke.sh` when generated files or template skill behavior changes.

For skill scripts, run syntax checks and representative script tests.
For `agents/openai.yaml`, validate YAML/TOML parsing through existing checks where applicable.
If SkillSpector is enabled or documented for the generated project, run `scripts/skillspector-scan.sh <skill-path>` before installing, updating, or vendoring external skills.

## Security And External Services

- Do not commit secrets, credentials, private tokens, or environment-specific identifiers in skills.
- If a skill uses MCP, Linear, graph memory, or another external service, document the service state and allowed read/write classes in external-service policy.
- External writes still require explicit user intent or a documented lifecycle command.
- Treat external skill source code as third-party code until reviewed and validated.
