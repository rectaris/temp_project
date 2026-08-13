# Route rendered-page tasks to an authorized browser backend

status: checked
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
  - template/.project-agent-workflow/ownership.yaml
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
  - The skill prefers configured and authorized Kitesurf only for short-lived, state-independent work within its documented compatibility boundary, and selects Cloudflare Browser Run's Chromium engine under the same service authorization for persistent state, video, WebGL, real-browser TLS challenge behavior, pixel fidelity, or compatibility failure; any Chromium provider outside Browser Run requires a separate policy record.
  - Browser reads and browser side effects are separate operations; form submission, publication, purchase, upload, account mutation, or another remote change requires write-capable policy plus current user authorization for the exact effect.
  - Fresh generated projects contain a disabled browser_run external-service record without connection data, account identifiers, or credentials; configured project-owned records may contain non-secret account identifiers and credential references but no raw credential, while Copier updates preserve project-owned external-service configuration byte-for-byte and remain valid when older projects have no browser_run record.
  - Fixed median, edge, and hold-out scenarios contain at least one critical requirement and cover Kitesurf selection, Chromium fallback, plain HTTP retrieval, unavailable-provider fallback, and denial of unauthorized side effects.
  - Static inventories, normalized root/template skill and backend-reference parity, generated discovery bridges, ownership reservations, structured scenario mappings, fresh-copy semantics, and supported Copier update behavior are checked deterministically.
checked_summary_ja: 描画済みページを必要とする依頼だけを認可済みブラウザへ送り、条件が合う場合にKitesurfを優先するルーティングを追加する。

## Context

The current policy routes agents to task-specific documents but has no route or reusable skill for deciding whether a request needs plain HTTP retrieval, a rendered browser, or a stateful Chromium session.

Kitesurf is an optional Cloudflare Browser Run backend with lower CPU and memory use for compatible short-lived tasks, but it is beta software and does not cover every browser capability.

## Decisions

- Route by the required browser behavior rather than by the Kitesurf product name or the presence of a URL.
- Name the task route `browser_automation`, the reusable skill `browser-ops`, and the generated-project external-service record `browser_run`.
- Define `browser_run` as the authorization record for the Cloudflare Browser Run service, whose configured connection can select either its Kitesurf engine or its default Chromium engine; a Chromium service outside Cloudflare Browser Run requires its own external-service record and authorization.
- Keep Browser Run disabled by default; fresh records contain no connection or account data, while configured project-owned records may keep non-secret connection metadata, account identifiers, and credential references but never raw credentials.
- Treat Kitesurf as a conditional first choice, not as the universal browser backend.
- Keep older generated projects valid when Copier updates add the managed route and skill but their preserved project-owned policy has no browser_run record; the skill must fail closed and use the documented fallback.
- Keep external side effects outside read authorization and require exact current user authorization in addition to write-capable policy.

## Tasks

- [x] Add root and generated routing for rendered-page and browser-interaction tasks.
- [x] Create the reusable browser-ops skill, generated discovery bridge, and backend-selection reference.
- [x] Add the disabled Browser Run policy record and managed setup/fallback guidance without storing credentials.
- [x] Add fixed evaluation scenarios and deterministic inventory, parity, generation, and Copier update checks.
- [x] Run all required validation and record accepted evidence.

## Validation Notes

Candidate `a5bb46c259de97c9f24be083ab5c1e46d8f4716205df5be38d9afe9128b4bfa3` was rejected during main-session review.

Candidate `e9d925d5c7eeb66a4e2f5839726f43c90d8ce5f8f54507789adeb1e5d2809906` was also rejected during main-session review because it moved the existing `security` conditional routes under `browser_automation` and used a nonexistent root reference path.

Candidate `d5c2aee9ff247fa8289e401773786da68385e3941b9ba213b6743fbc393b71af` was rejected because multiple root/generated skill paths did not resolve, Kitesurf was incorrectly restricted to read-only work, and unrelated existing external-service descriptions were rewritten.

Candidate `3d0c74ff25b8a1a4eca126a5b7e531e1a200d11c68a6b0f3c6434cb86c8dbc80` was rejected because the root route omitted the browser skill, the root skill omitted the template policy's `.jinja` suffix, and its update test used Copier's force flag.

The replacement candidate must:

- keep `SKILL.md` concise and move backend-selection details into a direct `references/` file in both the root and generated reusable skill;
- preserve the existing `security` task route and every existing conditional route exactly under its original task type;
- the root `.codex/skills/browser-ops/SKILL.md` must read `references/browser-run-policy.md`, `template/.project-agent-workflow/skills/browser-ops/SKILL.md` must also read `references/browser-run-policy.md`, and `template/.agents/skills/browser-ops/SKILL.md` must read `.project-agent-workflow/skills/browser-ops/SKILL.md`;
- the root skill must read `template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja` and `template/docs/agent/external-services.yaml.jinja`; the generated skill must read `.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md` and `docs/agent/external-services.yaml`;
- the root `browser_automation` route must require `.codex/skills/browser-ops/SKILL.md`, `.codex/skills/browser-ops/references/browser-run-policy.md`, and `docs/agent/SPEC_SECURITY.md` while preserving all existing routes;
- link `https://blog.cloudflare.com/kitesurf/` as the Cloudflare Kitesurf compatibility source and describe Kitesurf as beta; do not browse for another Kitesurf source;
- describe Kitesurf using supported properties such as lower CPU and memory consumption instead of an unsupported lower-latency claim;
- allow authorized, compatible, one-shot screenshots, PDFs, extraction, and automation on Kitesurf, while routing pixel-perfect output, video, WebGL, bot-challenge handshakes requiring real TLS fingerprints, long authenticated sessions, persistent state, and observed compatibility failures to Chromium;
- apply backend selection after classifying the operation as read or write, and require an exact `write_authorization_rule` match plus current-user authorization before any browser write;
- allow Kitesurf for compatible authorized reads or writes; write classification changes authorization requirements, not backend compatibility by itself;
- leave every pre-existing line in the `states`, `mcp`, `linear_sync`, and `graph_memory` blocks of `template/docs/agent/external-services.yaml.jinja` unchanged, and avoid unrelated README or policy rewrites;
- add a Copier update assertion proving that a project-owned older `external-services.yaml` without `browser_run` remains preserved and valid; and
- run that Copier update assertion without `-f`, `--force`, conflict acceptance, or any other bypass of the non-destructive update path; and
- avoid relying on a smoke run from an uncommitted clone as acceptance evidence, because the main session will rerun smoke after committing an accepted candidate if the test harness requires a committed source snapshot.

Final validation remains pending implementation acceptance.

Independent review of candidate `6def3c06ec4f1fb6a7da4c3cfb0c525961f2dae24c5c6f9baa67680f24fc9ab8` accepted the route and skill referents but rejected the external-service boundary and identified four validation gaps. The correction candidate must:

- state that `browser_run` authorizes Cloudflare Browser Run as one service and that Kitesurf and Chromium are engine choices behind the same configured Browser Run connection;
- require a distinct project-owned external-service record before using any Chromium backend outside Cloudflare Browser Run, so Browser Run authority cannot bleed into another provider;
- distinguish empty fresh defaults from configured project-owned identity: allow non-secret account identifiers and credential references in configured policy, but never raw credentials;
- reserve `.agents/skills/browser-ops/SKILL.md` in `template/.project-agent-workflow/ownership.yaml` and check the reservation deterministically;
- normalize and compare root/template `SKILL.md`, `agents/openai.yaml`, and `references/browser-run-policy.md` semantics so backend-selection guidance cannot drift;
- compare the complete older project-owned `external-services.yaml` byte-for-byte before and after the non-force Copier update;
- express backend-selection scenarios as structured conditions and deterministically verify each condition-to-route mapping rather than checking only an inventory of expected words; and
- make the Kitesurf and Chromium scenario requests explicitly assume a configured Browser Run record that authorizes the requested read or session, while retaining the disabled-provider and unauthorized-write cases.

Correction candidate `f1b9297e0457fdba938953d7259daffb930cee8f3327a800871793583086791e` was rejected during main-session review. It made the root backend reference read the generated-project path `docs/agent/external-services.yaml`, which does not exist at the repository root, and left the Kitesurf and Chromium request text ambiguous even though it added separate structured conditions. The next candidate must:

- make the root backend reference read `template/.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md.jinja` and `template/docs/agent/external-services.yaml.jinja`;
- make the generated backend reference read `.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md` and `docs/agent/external-services.yaml`;
- compare the two references after normalizing those root/generated path pairs, rather than requiring byte equality; and
- state the configured Browser Run authorization premise in each of the `kitesurf-pdf` and `chromium-webgl` `request` strings as well as in their structured conditions.

Correction candidate `eca754173cac9fd33e1ed136ef716e95cc881427522a9e7f82d876b8103b2d49` was rejected during main-session review because its parity check omitted `SKILL.md`, and two structured cases confounded their intended decision variable. The next candidate must:

- normalize and compare the root/generated `SKILL.md` path pairs in addition to the backend reference and `agents/openai.yaml`;
- model `provider-unavailable` as an authorized Browser Run service with `provider_available: false`, keeping authorization separate from availability; and
- model `unauthorized-submit` with an allowlisted operation and matching exact write rule but `current_user_authorization: false`, so current user authorization is the only failed write gate in that hold-out case.

Candidate `fce0a650716a819557a643b223ece1eee2260b20edca387c00f37013f17073b7` was accepted after main-session diff review and applied through `scripts/run-sandboxed-plan-worker.py`.

Final validation passed:

- `python3 scripts/check-root-agent-policy.py`
- `python3 scripts/check-copier-template.py`
- `scripts/lint-project-workflow.sh`
- `tests/smoke.sh`
- `REQUIRE_COPIER=1 tests/copier-update.sh`
- `python3 scripts/validate-changes.py --all`
- `git diff --check`
- skill-creator `quick_validate.py` for both root and generated `browser-ops` skills
- required referent contract check with independent semantic review

Independent scenario evaluation classified all five fixed cases as expected and found no unresolved ambiguity. Independent change review found no remaining High or Medium issue and passed all three controlled referents. The accepted Low residual is that deterministic checks validate policy markers and scenario mappings rather than executing the natural-language policy as code; independent evaluation supplies the semantic check for the current artifact. `actionlint` was unavailable and the existing smoke harness reported its optional GitHub Actions lint step as skipped. Live Browser Run access was not configured or exercised; generated projects remain disabled by default and fail closed.
