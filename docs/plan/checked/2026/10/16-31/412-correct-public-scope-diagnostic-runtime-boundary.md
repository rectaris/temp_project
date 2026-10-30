# Correct the public advisory scope diagnostic runtime and child boundary

status: checked
primary_invariant: Public Root/generated advisory diagnostics observe declared files only as bounded data and clean owned children under the accepted trusted-runtime boundary, without executing inspected data, weakening ordinary public authoring, or granting authority.
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
  - {"evidence":"Public479 Root/generated reproduce declared future dependency hardlink execution, a stopped probe exceeding32.5 seconds, and plain Root command-directory bytecode. Historical CI success does not clear these failures; PR43 stays draft.","kind":"reproduced_defect"}
  - {"evidence":"Private product f244d904199ff0572c56a015df637ed378a6b06b is independently accepted and normally published; Plan508 is uniquely checked at4fed1137d181e7fbd326145151292fe8af9a4262. Its actual Root/generated CLI, semantic, fresh/update Copier and unchanged mandatory witnesses pass.","kind":"existing_mechanism"}
  - {"evidence":"Exact AST comparison public479/private accepted product: ordinary check matches after removing only scope branches, and the helper observation body matches. Public52 methods include seven public-only cases; adapt thirteen private-only consumer regressions plus one owned-runtime fixture, never whole private authoring/test files.","kind":"mechanical_transformation"}
  - {"evidence":"Existing public package already registers the diagnostic helper and fresh/update consumer regression entry. Correct within existing Root/template paths; preserve ordinary rendering, source identities, unknowns, optional YAML and public-only unassigned/reason behavior.","kind":"existing_mechanism"}
  - {"evidence":"Public fixture_clone uses committed HEAD, then overlays only68 existing inventory paths. The planned guidance and shell paths are absent. Add those exact existing template paths to the established inventory so actual fresh/update fixtures receive the corrected candidate, without changing the loop or validation.","kind":"mechanical_transformation"}
completion_conditions:
  - Actual public Root/generated diagnostics retain bounded declared syntax/static observations and unknowns while refusing runtime/data overlap or unavailable ownership observation, never executing inspected source and bounding owned child cleanup.
  - All original public structured/legacy/unassigned-reason, ordinary/digest-only/structural-refusal and generated shell behavior is retained, with no inspected-input mutation or command-directory bytecode from plain Root checks.
  - Actual fresh and supported updated Copier consumers run the corrected installed diagnostic contract with retained project-owned code, policy, configuration, history and unchanged validation.
completion_witness_map:
  - {"condition_sha256":"sha256:e2ab0c972cfbf2062b931eef231fe825a7ec6dda4f863ff1d6a77fdff517d2e1","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:0a6fca4cfdede72ba2f02f9df01b5259a8c6113674a6c66313a81707f5907f1c","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:d7e9144361cf72bef19b8fe94f687c0562053d38f1bb24f7d13bec79c09e4d27","witness":"tests/copier-update.sh --require-copier"}
write_scope:
  - scripts/project_workflow/plan_scope_candidates.py
  - template/.project-agent-workflow/scripts/plan_scope_candidates.py
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - scripts/create-root-plan.py
  - template/.project-agent-workflow/scripts/create-plan.sh
  - docs/agent/SPEC_DECISION_AUDIT.md
  - template/.project-agent-workflow/docs/agent/SPEC_DECISION_AUDIT.md
  - tests/validation_tools/plan_authoring.py
  - tests/copier-update.sh
  - CHANGELOG.md
  - tests/fixtures/orchestration/copier-update-source-inventory.txt
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
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
  - python3 tests/test-validation-tools.py
  - tests/copier-update.sh --require-copier
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Actual public Root and generated check CLIs observe declared files only as bounded data, retain syntax/static evidence and honest unknowns, refuse physical runtime overlap or unavailable child custody, and clean owned groups without inspected-source execution or authority expansion.
  - Existing52 public consumer cases, including all seven public-only ordinary features, remain intact alongside thirteen new counterexamples; structured/legacy authoring, ordinary checks, raw digest-only, failures and shell check-only semantics preserve input/data and command-directory bytes.
  - Corrected Root/template semantics pass actual fresh and supported updated Copier consumers without losing project-owned artifacts, policy, configuration, plan history or unchanged validation; no new package, controller adoption or inferred operational completeness is introduced.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:41c6e25745841828f69353f389035fbd14ba4e06f19b3f0029ef06b1819a8b16","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:87dfc81585ebbd69f0d1559fea19850d3e58620d0d51594cbf5b80c5ee7b1ac6","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:123893e0466c40ce1490c857b5b21f7cd7517a3f9c5f0b501199beaef6350bf9","stage":"focused","witness":"tests/copier-update.sh --require-copier"}
checked_summary_ja: 公開側のスコープ診断で非実行と子プロセスの終了管理を修正した。

## Decisions

- Use exact public branch rectaris/pr-static-scope-foundation at479 as source, not private dev. Accepted private f244 and checked508 at4fed are evidence for a function-level adaptation only; do not copy unrelated private authoring, tests or policy.
- Keep the three public acceptance items and full semantic/Copier focused witnesses plus both unchanged mandatory commands. Adapt13 consumer counterexamples and one owned-runtime fixture while retaining all52 originals and seven public-only tests; do not pin implementation text or test mock forwarding.
- Within existing helper paths, activate the same builtin-first physical guard before site/dependencies and retain bootstrap guard state for exit callbacks; bind checked scope argv/JSON and preserve actual optional YAML. Keep trusted stable Python/helper assumptions, honest unknowns and no full runtime-closure/OS-sandbox claim.
- Adapt only probe/deadline/candidate-report functions, their scope-only check branches and the obsolete public-main scope gate; retain public ordinary build/render/main behavior. Verify exact native FD/P_PID/PGID/SID/group signalling and bounded cleanup before effects; no unsafe fallback or raw clone.
- Include Root entrypoint and generated shell explicitly. Prove plain Root without -B and keep generated diagnostic check-only behavior; ordinary and digest-only paths remain independent of optional Linux/native diagnostics.
- Keep Root/template policy/tooling aligned through existing delivery/parity/inventory checks. Existing fresh/update common hook may need no edit; do not add a no-op solely to occupy its declared path.
- Parent owns implementation, exact-source independent native review, unchanged validation, acceptance, commits and normal local publication/retirement. Use actual owner-bound prospective policy and accepted parent controls; preserve historical public policy, all138 known registry admissions, old findings/stops and unknown consumption. Never fabricate legacy/schema8 evidence, reset a count or operate source478.
- Implementation starts only from this normally published checked-authoring plan in its own managed task. Preserve checked_summary_ja and all protected fields during later normal completion; append actual notes only.
- After local exact-scope acceptance and normal same-plan closeout, refresh public base/head/account/owner/publication gates, push only the accepted scoped branch and verify same-head CI/review before updating public quality and leaving draft. No private-dev remote push, main merge, release, PR24 mixing, credentials/provider/model change or controller adoption. Whole Issue16 stays open for responsibility and maintainability work.
- Include the exact existing Copier update source inventory. Its committed-clone/overlay boundary otherwise leaves changed template guidance and shell at old HEAD during working-tree validation. Add only those two existing template paths; retain the loop, ownership and full actual-consumer checks.

## Tasks

- [x] Confirm exact public baseline and source/package ownership; map the accepted safety functions to existing public callers without changing ordinary authoring contracts.
- [x] Adapt Root/template guarded helper, native probe/deadline/report path, Root bytecode boundary and generated check-only invocation while retaining syntax/static observations and optional YAML.
- [x] Adapt all thirteen behavioral counterexamples and the owned-runtime fixture while preserving all52 original public cases; exercise actual Root/generated ordinary/diagnostic CLIs and real fresh/update consumers.
- [x] Align existing runtime/ownership prose and changelog; obtain exact-target independent source assessment and run full semantic, actual Copier and both unchanged mandatory witnesses in this task own locked environment.
- [x] Accept/commit only the in-scope correction, normally publish to the exact public local source and retire its task, normally complete/archive this same Tier2 plan without protected-field edits, then use fresh scoped GitHub gates for ordinary branch update, same-head CI/review and accurate Issue16 evidence.

## Validation Notes

- Private accepted product and metadata are limited feasibility evidence, not public adapted-target acceptance. Public479 remains draft with actual defects despite historical six-check CI success.
- Readonly transfer boundary07 compares actual source bodies and identifies seven public-only tests to retain and thirteen new consumer methods to adapt. Whole proposed public patch has not been generated or executed.
- Fresh startup public43-safety-startup03 checked exact baseCDF/head479 with no blockers; its semantic completeness, exclusive-writer and branch-rule uncertainties remain for main-owned review and fresh prepublication.
- The primary owner policy necessity-1 retains its actual Issue18 quotation and existing accepted controller7501; this task adopts no new operational controller. Public snapshot lacks delegation-policy.json at the known path; do not import private policy or reinterpret old public counts as prospective ceilings.
- Authoring custody explicitly binds public branch. The first empty preparation defaulted to configured private dev, wrote no plan/product bytes and was normally retired with supported stranded-record recovery before explicit-source re-preparation.
- No current public verification, remote push, merge, release, authority expansion or Issue closure is inferred. Keep all original requirements, safety conditions, counts, old stops and unknown history.
- Input04 used integer2 where the established authoring schema requires string2; official check refused before any plan write. Input05 changes only that representation, not the selected Tier2 or any requirement/scope/validation.
- Accepted external private CLI scope projection05 emits30 advisory rows. All exact counterparts are already declared; unknown dynamic/literal registration rows remain unknown, not automatic edits. Parent reads the actual68-path inventory and committed clone/overlay loop and expands checked authoring scope to12 before any plan/product write; actual updated consumers remain required.
- Checked authoring published the original protected plan as d6686f568ccfda4e63f84ed8793d7cf29c77ccca. Parent implementation stays within its twelve exact paths; ten change. Generated shell already has the required check-only/-B path and the existing Copier hook already invokes the installed consumer, so neither receives a no-op edit. All52 original class cases and all seven public-only features are preserved; thirteen adapted methods and two additional metadata/sentinel counterexamples yield67 class cases.
- The adapted shared renderer also refuses helper, entrypoint, interpreter and loaded-module source/cache roles before opening targets. Intrinsic module namespaces avoid lazy/subclass attribute callbacks; exact str/bytes metadata preserves physical checks without custom conversion; nonnull unsupported metadata fails closed and import-blocking None is skipped. Both copies remain byte-identical. Helper guard, descriptor exception, native capability checks and WNOWAIT-held leader custody retain their documented trusted-runtime, exclusive-child-reaping and stable-policy conditions; no hostile-reaper/full-closure/OS-sandbox guarantee is added.
- Actual before/after fixtures cover four direct-role omissions, two namespace callbacks, eight typed-metadata omissions and two import-sentinel failures. All corrected counterexamples refuse or succeed as appropriate without input/data mutation or execution marker. Actual17-case smoke and four Root/generated ordinary/diagnostic CLI paths pass; exact helper observation/probe/deadline bodies and original ordinary public behavior are retained.
- Parent retains all actual assessments139-142 and their patches, receipts, successful tests, findings and unknown history. The first High claim is independently rejected only inside the unchanged exclusive-reaping contract, not by weakening it. Confirmed direct-role, namespace, typed-path and sentinel findings are repaired within this scope. Final exact-source session01a186e1-5bb3-7c02-93cb-d02b72ea0355, receipt sha256:43e0105db67bbb0704443b6bb19c95ac33f22f6ac98313252a6a2e2384793e0a, is admitted once at registry event142 and reports No High/Medium/Low. Configured Sol/high is not evidence of resolved provider identity; no count reset, source478 operation or prospective-controller adoption occurs.
- Exact product patch sha256:2e4826bc54ccf21de82b4fa484dd9ec6a7dbdb5f750991db39cce867baef4f62 passes all four unchanged commands in its own locked environment: python3 tests/test-validation-tools.py (493 tests), tests/copier-update.sh --require-copier (actual fresh/updated consumers), scripts/lint-project-workflow.sh and tests/smoke.sh, each exit0. Root/template policy/tooling delivery and exact source inventory align; project-owned data/configuration/policy/history and original validation remain intact.
- Parent acceptance80 binds all three unchanged acceptance items to these actual focused/mandatory results and independent source clearance. Commit296cd178a3a1d4db7b5e1c4d54e72b16b52c6668 is normally published81 to this exact public local source; its implementation worktree and temporary branch are removed. No private-dev product is imported or pushed.
- Parent order audit64 uses the permitted equivalent implementation order to avoid checking a future remote effect: accept and normally publish product; push that product while Draft and observe exact-head CI; normally close this same plan; then publish lifecycle metadata and verify final-head CI before public quality/Ready. It changes no original requirement, safety/acceptance condition or external-effect authority. This normal same-plan lifecycle transaction preserves the original protected summary/header/conditions/maps and creates no new lifecycle-only numbered plan.
- Old prepublication82 refuses a changed selection/artifact against its479 startup. That refusal remains preserved. Fresh startup83 binds the accepted296 product and all27 declared required assets, including checked411; unchanged prepublication84 passes with no blockers. Semantic dependency completeness, exclusive-writer and branch-rule limits remain explicit and are resolved only by parent exact-package review and ordinary nonforce publication, not by claiming the gate proves them.
- Separately authorized ordinary push86 updates only rectaris/pr-static-scope-foundation from479 to296. GitHub readback92 verifies that exact HEAD and six successful checks under run40847159318: plan-restructure, minimum-compatibility, copier-fixture-validator, validate, plan-execution-state and sandboxed-plan-worker. GitHub reviews/comments are both0, not inferred owner approval. PR43 stays Draft/open/unmerged and Issue16 exact readback95 records actual product evidence without checking final-metadata quality.
- Final lifecycle metadata remains subject to its own unchanged lint/smoke, parent acceptance, normal exact-source publication/retirement, fresh scoped push and final same-head CI before Ready/public-quality completion. No main merge, release, private-dev push, PR24 mixing, credential/provider/model change or operational adoption is claimed. Current private4fed residuals require a separate admitted correction, historical Plan508 stays untouched, and whole Issue16 remains open for responsibility/boundary/maintainability work.
