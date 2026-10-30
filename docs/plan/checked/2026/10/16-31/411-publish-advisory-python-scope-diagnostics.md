# Publish bounded advisory scope correspondence and Python import observations

status: checked
primary_invariant: The explicit scope diagnostic reads only bounded declared data, preserves unknowns and grants no write, validation, execution or acceptance authority; ordinary authoring stays unchanged.
task_types:
  - template_workflow
  - planning_docs
  - security
  - task_worktrees
  - external_services
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Accepted 343dbbbe4278adc7f755211e5d5ef4502e6d3195 ships standalone plan_scope_candidates.py (sha256:2fcc63e025fd72a406e3ac230048bd8eb28d388b6f2bfa57da835948f73f49ea). Python/JSON observations use stdlib; YAML correspondence optionally uses existing PyYAML and stays unknown without it. No execution-controller import.","kind":"existing_mechanism"}
  - {"evidence":"The parent ran that exact accepted module against an isolated temporary pkg/a.py -> pkg/b.py fixture plus an explicitly missing source. Direct and transitive dependents matched the declared subgraph, the missing source retained null dependent sets, grants_authority stayed false and repository fixture bytes stayed unchanged. This is not proof of a public CLI or installed consumer.","kind":"bounded_prototype"}
  - {"evidence":"Owner-merged public dev cd7f81b46b0f1e5c9b3c7802ee8221bca47d29dd already provides checked root/generated authoring, mirrored library alignment, source/generated delivery inventories and real Copier copy/update consumers. Add only the explicit option and this module family; do not replace the authoring implementation or port intervening private history.","kind":"mechanical_transformation"}
  - {"evidence":"Actual probes: PyYAML yields covered YAML correspondence; -S absence yields unknown while Python observations stay parsed and fixture bytes unchanged. Declared script/yaml.py executed under normal lookup but stayed unexecuted with Python -I -B. This supports isolated diagnostics, not full runtime closure.","kind":"bounded_prototype"}
completion_conditions:
  - The opt-in root and generated Python CLI reports registered correspondence and digest-bound syntax/static relative-import observations only for declared bounded data, retaining unknowns and never executing inspected source or implying runtime completeness.
  - The generated shell forwards the explicit diagnostic only in check mode; digest-only output, default checks, structural refusals and repository command-directory contents retain their prior contracts.
  - Actual fresh and updated Copier projects receive and exercise the diagnostic family with semantic checks, without loss or weakening of project-owned artifacts or validation.
completion_witness_map:
  - {"condition_sha256":"sha256:9af999dde2fcedd848fc4bce886e4f9c2b5acbed9ef98fb0e958c91ce2ea9e79","witness":"python3 tests/test-validation-tools.py PlanAuthoringTest"}
  - {"condition_sha256":"sha256:c7be6632d5089145a2118c57f6b29f644305c3c43086997baa7dc276d66b7bc0","witness":"python3 tests/test-validation-tools.py PlanAuthoringTest"}
  - {"condition_sha256":"sha256:34cc1629f9d711d9de80742442c302b87c86c516336b44041ed93f0154cd0ac8","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - scripts/project_workflow/plan_scope_candidates.py
  - template/.project-agent-workflow/scripts/plan_scope_candidates.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - template/.project-agent-workflow/scripts/create-plan.sh
  - docs/agent/SPEC_DECISION_AUDIT.md
  - template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md
  - scripts/check-copier-template.py
  - scripts/project_workflow/copier_inventory.py
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
  - tests/validation_tools/plan_authoring.py
  - tests/copier-update.sh
  - CHANGELOG.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - scripts/create-root-plan.py
  - scripts/project_workflow/worktree_guard.py
  - docs/agent/git-retirement.yaml
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_AGENT_LOGGING.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_REFERENT_FIRST.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py PlanAuthoringTest
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Actual root and generated Python check commands expose the accepted advisory registration, Python-source and observed relative-import/reverse-dependent records with source evidence and honest unknowns; inferred source, inspected-source execution and authority expansion are absent.
  - Actual generated shell check and digest-only paths preserve ordinary authoring behavior and structural refusals; the new option cannot select write mode, mutate declared input or create command-directory bytecode.
  - The semantic diagnostic contract succeeds on actual fresh Copier output and supported updated consumers, with complete delivery registrations and preserved project-owned content, configuration, policy, plan history and validation behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:da527ddc74fe482c035a489baedd64973b1282da8e29f00c4c4f7ecd8e589a61","stage":"focused","witness":"python3 tests/test-validation-tools.py PlanAuthoringTest"}
  - {"acceptance_sha256":"sha256:8cb817f8a182dfaea7e40a23c2202f35e7a093a7a53b779b16c2aa0e4d5b2f39","stage":"focused","witness":"python3 tests/test-validation-tools.py PlanAuthoringTest"}
  - {"acceptance_sha256":"sha256:7788ceebd3e2a17f9968086dfd475407f4740e39196bcebf9c9debbfc8e8fb12","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 宣言済みの変更範囲について、登録対応とPythonの構文・相対import・利用元候補を表示する機能を公開した。

## Decisions

- Base this independent PR on the owner-merged public dev prerequisite cd7f81b46b0f1e5c9b3c7802ee8221bca47d29dd, not private dev, PR24 or unmerged PR42. Use the exact task-bound authoring and implementation worktrees and normal parent-owned publication.
- Port the accepted standalone diagnostic module and narrowly add the opt-in root/generated CLI and shell integration. Keep default authoring, existing structural checks and digest-only output unchanged; do not transplant unrelated authoring or controller changes.
- Keep registration evidence and syntax/static-graph observations advisory. Missing catalogs or unsupported correspondence remain unknown; add no missing policy catalogs, inferred file reads, runtime dependency guarantee, prohibited-import policy, scope expansion or automatic edits.
- Use Tier2 with three semantic acceptance items. Reuse established test loading and actual Copier consumers; do not add wording, copied-source or forwarding-only assertions as permanent tests.
- The public source does not yet expose the new option. Admit this first implementation through the existing checked authoring and parent-owned explicit first-installation authorization; never use the candidate option or candidate controller as its own authority. Preserve source478, historical refusals, unresolved findings and unknown consumption.
- The main session owns interpretation, writes, independent exact-target assessment, unchanged focused/authoritative validation, commits, normal publication and reporting. Independent source assessment is not a formal execution receipt or operational controller adoption.
- The GitHub goal is a narrowly scoped public PR and fresh actual-head CI observation. Perform only separately policy-authorized ordinary pushes and public PR/Issue communication; no force push, private-dev push, main merge, release, credentials change or operational controller adoption.
- Keep optional PyYAML correspondence and honest unknowns rather than stripping functionality to match the corrected dependency description; introduce no new package, catalog or controller dependency.
- Run the diagnostic helper in a fixed-argv isolated non-bytecode Python child with a minimal environment and JSON data containing only the already checked root, profile and declared paths. Do not compile the diagnostic module in the authoring process, import an inspected dependency-name shadow, add a filename exception or fall back to direct in-process execution. Keep ordinary authoring and digest-only behavior unchanged.
- Digest-only suppression belongs to the existing root/generated Python check CLI. The generated shell adds only the existing family check option; do not invent a new shell digest-only interface.

## Tasks

- [x] Port the accepted diagnostic family with the minimum root/generated CLI and shell option integration, using isolated diagnostic execution inside the declared paths rather than in-process dependency lookup.
- [x] Register the module in established source, generated-delivery and update-fixture inventories and mirrored alignment checks; document only actual advisory behavior and limits.
- [x] Reuse and adapt semantic root/generated CLI cases, including actual installed fresh/update consumers and dependency-name shadows that must stay unexecuted, without introducing unrelated catalog or execution-policy assets.
- [x] Obtain an independent exact-target source assessment and run the focused commands plus unchanged authoritative lint and smoke in this task checkout own locked environment; retain actual results and stop on authoritative failure.
- [x] Publish only the accepted commit through the normal managed-worktree path, create the independent PR, observe exact-head CI and applicable reviews, then archive this same plan through normal parent-owned lifecycle steps.

## Validation Notes

- Planning feasibility is bounded and does not establish public, generated or updated behavior; those require the declared actual consumer checks.
- The diagnostic option unavailable in the old public source is not invoked or fabricated for this plan own admission; no missing current-work policy, stopped run or absent historical receipt is repaired by copying candidate control.
- The initial fast-forward attempt could not resolve the API-observed public merge commit locally. A policy-authorized exact-origin fetch acquired that public object, after which the same exact fast-forward succeeded. No private branch was fetched or merged.
- PR42 remains an independent open/unmerged prerequisite-free public change at 1f170876c4099ee30053c850bf7038c0733e430d with CI 40731982041 all six successful; this plan does not adopt its controller, reopen source478 or clear whole Issues 16,18,23.
- Before plan publication, direct source reading corrected the unqualified stdlib-only assumption: PyYAML is optional for YAML correspondence. Protected original claims, probes and metadata results remain retained; no whole runtime closure is inferred.
- The confirmed import-shadow counterexample invalidated in-process diagnostic loading. Preserve the same requirements, 13-path scope, acceptance and validation while selecting isolated diagnostic execution and a consumer-visible regression before implementation.
- The allocator reads published source state rather than an ahead task checkout. The parent refused the provisional 388 preview, normally published only owner-merged cd7f81b first, then resumed the same logical task and normally allocated 411 under the shared lock; no unwritten reservation was marked written and no execution or review budget was reset.
- The accepted thirteen-path product patch is sha256:e43d037612772a9d4495afdced02eefcb36ff877f84a6bfe178caf6d10748820, committed as d380032c6fc27111d373d90c852e8a62ee10176c. Parent acceptance bound the actual committed patch to the reviewed patch and all three unchanged semantic acceptance witnesses before normal managed publication; the implementation task checkout and temporary branch were removed by that publication.
- In that implementation checkout's own locked environment, `python3 scripts/validate-changes.py --all --json`, the 52-case `python3 tests/test-validation-tools.py PlanAuthoringTest`, actual `tests/copier-update.sh --require-copier`, unchanged `scripts/lint-project-workflow.sh` and unchanged `tests/smoke.sh` all exited zero on the accepted target. Actual fresh and updated consumers exercised the installed diagnostic contract and retained project-owned artifacts and validation.
- Separate actual Root and generated CLI runs on the same final source observed digest-bound reverse dependents, null unknowns for a missing source, unchanged fixture bytes and unexecuted declared dependency-name shadows. Those offline distribution probes are not substituted for the real Copier witnesses.
- Earlier High/Medium/Low findings and their actual consumption remain retained. Parent probes reproduced runtime/data overlap execution, output/framing defects, successful-leader residual locks, inherited-pipe false failure and hidden Linux SA_NOCLDWAIT before correction, and observed the corrected refusals, bounded output and owned-group cleanup afterward. The scope-overrunning second review was rejected as clearing evidence and recorded in the parent operational security audit; no credential disclosure was established.
- The exact final source-only independent assessment04 returned no High, Medium or Low findings; its receipt is sha256:4a0129665ff7f90d8dcb56e18708f5a6a12368e8eb8ad83541e861630d4fc0b4. Its runtime contained no successful filesystem or command-tool execution. Source assessment is not independent validation, a normal execution receipt, full runtime/OS-sandbox closure or operational controller adoption. The original third-review validation overclaim and its append-only correction remain preserved; only the later actual final-target results supported product acceptance.
- PR43 https://github.com/rectaris/temp_project/pull/43 published only the public-base authoring and accepted product commits. Actual pull_request CI 40765806813 at d380032c6fc27111d373d90c852e8a62ee10176c passed all six jobs, with stable observed public base cd7f81b46b0f1e5c9b3c7802ee8221bca47d29dd and zero submitted reviews or review comments at that observation. PR43 was open/unmerged. Private dev, whole Issues 16/18/23, source478, main merge, release and operational adoption remain unchanged; this closeout preserves Tier2, requirements, acceptance, witness authority and all historical stops and consumption.
