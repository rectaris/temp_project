# Route rendered-page tasks to an authorized browser backend

status: in_progress
task_types:
  - planning_docs
  - template_workflow
  - security
  - skill_authoring
  - referent_first
review_class: B
human_design_required: no
human_approval_status: not_required
write_scope:
  - .codex/skills/browser-ops/
  - docs/agent/spec-index.yaml
  - references/routing.md
  - scripts/check-copier-template.py
  - scripts/check-root-agent-policy.py
  - template/.agents/skills/browser-ops/
  - template/.project-agent-workflow/AGENTS.md.jinja
  - template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja
  - template/.project-agent-workflow/docs/agent/spec-index.yaml.jinja
  - template/.project-agent-workflow/skills/browser-ops/
  - template/README.md.jinja
  - template/docs/agent/external-services.yaml.jinja
  - tests/assert-generated-semantics.py
  - tests/copier-update.sh
  - tests/fixtures/browser-ops/
  - tests/smoke.sh
context_files:
  - AGENTS.md
  - copier.yml
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - template/.project-agent-workflow/ownership.yaml
  - template/.project-agent-workflow/scripts/check-external-service-policy.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_SKILL_AUTHORING.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - python3 scripts/check-root-agent-policy.py
  - python3 scripts/check-copier-template.py
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Root and generated-project routing select browser policy only for requests that require JavaScript-rendered page state, browser-produced artifacts, DOM inspection, or browser interaction; a plain URL lookup remains outside this route.
  - A concise reusable browser-ops skill applies the project external-service gate before provider access and keeps detailed backend-selection guidance in one direct reference.
  - The skill prefers configured and authorized Kitesurf only for short-lived, state-independent work within its documented compatibility boundary, and selects an authorized Chromium-capable fallback for persistent state, video, WebGL, real-browser TLS challenge behavior, pixel fidelity, or compatibility failure.
  - Browser reads and browser side effects are separate operations; form submission, publication, purchase, upload, account mutation, or another remote change requires write-capable policy plus current user authorization for the exact effect.
  - Fresh generated projects contain a disabled browser_run external-service record without account identifiers or credentials, while Copier updates preserve project-owned external-service configuration and remain valid when older projects have no browser_run record.
  - Fixed median, edge, and hold-out scenarios contain at least one critical requirement and cover Kitesurf selection, Chromium fallback, plain HTTP retrieval, unavailable-provider fallback, and denial of unauthorized side effects.
  - Static inventories, root/template skill parity, generated discovery bridges, fresh-copy semantics, and supported Copier update behavior are checked deterministically.
checked_summary_ja: 描画済みページを必要とする依頼だけを認可済みブラウザへ送り、条件が合う場合にKitesurfを優先するルーティングを追加する。

## Context

The current policy routes agents to task-specific documents but has no route or reusable skill for deciding whether a request needs plain HTTP retrieval, a rendered browser, or a stateful Chromium session.

Kitesurf is an optional Cloudflare Browser Run backend with lower CPU and memory use for compatible short-lived tasks, but it is beta software and does not cover every browser capability.

## Decisions

- Route by the required browser behavior rather than by the Kitesurf product name or the presence of a URL.
- Name the task route `browser_automation`, the reusable skill `browser-ops`, and the generated-project external-service record `browser_run`.
- Keep Browser Run disabled by default and keep connection metadata, account identifiers, and credential references in project-owned external-service configuration.
- Treat Kitesurf as a conditional first choice, not as the universal browser backend.
- Keep older generated projects valid when Copier updates add the managed route and skill but their preserved project-owned policy has no browser_run record; the skill must fail closed and use the documented fallback.
- Keep external side effects outside read authorization and require exact current user authorization in addition to write-capable policy.

## Tasks

- [ ] Add root and generated routing for rendered-page and browser-interaction tasks.
- [ ] Create the reusable browser-ops skill, generated discovery bridge, and backend-selection reference.
- [ ] Add the disabled Browser Run policy record and managed setup/fallback guidance without storing credentials.
- [ ] Add fixed evaluation scenarios and deterministic inventory, parity, generation, and Copier update checks.
- [ ] Run all required validation and record accepted evidence.

## Validation Notes

Candidate `a5bb46c259de97c9f24be083ab5c1e46d8f4716205df5be38d9afe9128b4bfa3` was rejected during main-session review.

Candidate `e9d925d5c7eeb66a4e2f5839726f43c90d8ce5f8f54507789adeb1e5d2809906` was also rejected during main-session review because it moved the existing `security` conditional routes under `browser_automation` and used a nonexistent root reference path.

The replacement candidate must:

- keep `SKILL.md` concise and move backend-selection details into a direct `references/` file in both the root and generated reusable skill;
- preserve the existing `security` task route and every existing conditional route exactly under its original task type;
- use `references/browser-run-policy.md` from each `SKILL.md`, or another path that resolves from both installed skill locations;
- link `https://blog.cloudflare.com/kitesurf/` as the Cloudflare Kitesurf compatibility source and describe Kitesurf as beta; do not browse for another Kitesurf source;
- describe Kitesurf using supported properties such as lower CPU and memory consumption instead of an unsupported lower-latency claim;
- allow authorized, compatible, one-shot screenshots, PDFs, extraction, and automation on Kitesurf, while routing pixel-perfect output, video, WebGL, bot-challenge handshakes requiring real TLS fingerprints, long authenticated sessions, persistent state, and observed compatibility failures to Chromium;
- apply backend selection after classifying the operation as read or write, and require an exact `write_authorization_rule` match plus current-user authorization before any browser write;
- add a Copier update assertion proving that a project-owned older `external-services.yaml` without `browser_run` remains preserved and valid; and
- avoid relying on a smoke run from an uncommitted clone as acceptance evidence, because the main session will rerun smoke after committing an accepted candidate if the test harness requires a committed source snapshot.

Final validation remains pending implementation acceptance.
