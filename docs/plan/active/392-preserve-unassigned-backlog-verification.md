# Preserve unassigned backlog verification without implementation authority

status: in_progress
primary_invariant: An unstarted backlog may retain truthful unassigned verification with a concrete reason, but that representation never authorizes activation, implementation or acceptance and never replaces original requirements or safety restrictions.
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: approved
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"At public source ba8657ba, root create-root-plan.py check exits1 for preserved plan387 input: acceptance_items entry1 must declare witness and stage. The shared reader permits its unmapped backlog; the conflict is retained in local exact-command evidence.","kind":"reproduced_defect"}
  - {"evidence":"Shared plan_authoring.py derives coverage and renders root/generated manifests. Canonical planlib.py already validates witness maps and owns promotion/completion checks; registered validation_tools plan and authoring tests cover these entrypoints. No new runner or review route is needed.","kind":"existing_mechanism"}
completion_conditions:
  - Structured unstarted backlog authoring retains each acceptance item with its declared future witness or a bounded concrete unassigned reason, rejects a missing/blank/placeholder reason and conflicting declaration, and derives every digest from original text.
  - The checked plan387 input and its regenerated supported sections retain every E1-E5 acceptance/condition string and source-order digest, all four fixture predicates and all published safety restrictions, with backlog status and every whole requirement unmet.
  - Any remaining unassigned verification refuses active authoring, promotion, implementation-start and acceptance before a repository or runtime effect; no fake command, receipt, success, restored whole offline mapping or refusal retry grants authority.
  - Fully assigned root/generated authoring and the generated legacy conversion retain their accepted behavior and rendering; root/template policy and authoring bytes remain aligned and focused/authoritative validation authority is unchanged.
completion_witness_map:
  - {"condition_sha256":"sha256:c74fbffbcb49348a1b754a462991486c2d95a79effa31495e23e439328f88e58","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:24fb66d8dd2e949009b9dd58835c608d222ae00f39b44f6b95d94f30daefb137","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:95c3a482dd64b96b4d8ed5c74b3c7576cdf1f01b30dd3c9b5b0f4fbc26c130af","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:437bb07417efe09bfeb78372518a48d5b3bf8842d9538641043e7d53d9ce35a1","witness":"python3 tests/test-validation-tools.py"}
write_scope:
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/plan_authoring.py
  - template/.project-agent-workflow/scripts/planlib.py
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - template/.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md
  - tests/validation_tools/plan_authoring.py
  - tests/validation_tools/plan.py
  - docs/plan/backlog/387-implement-issue18-limited-implementation-resume.md
  - docs/plan/authoring/387-implement-issue18-limited-implementation-resume.json
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - scripts/create-root-plan.py
  - scripts/plan_validation_commands.py
  - tests/test-validation-tools.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_DECISION_AUDIT.md
  - docs/agent/SPEC_GIT_RETIREMENT.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_AGENT_LOGGING.md
focused_validation:
  - python3 tests/test-validation-tools.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - Unstarted backlog preparation preserves truthful unassigned verification and plan387's complete E1-E5 requirements and safety restrictions without creating activation or acceptance authority, while fully assigned and historical reading paths retain their established behavior.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:26f751b2d83893a1d445df220e51cd15a298c8a8b8c9f97f1e57e5b81c72fd92","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
integration_gates:
  - Authoring is a direct task, not product execution. Before any declared code/policy/test implementation, formally publish this active plan to the exact bound PR20 source and prepare its separate implementation task. Publication requires exact new cleanup authority; none is inferred from specification approval or the separate plan389 task.
  - Use the adopted bounded parent-direct path because the declared scripts/tests/template control paths are protected from candidate-worker generation. Bind a fresh task-specific execution ledger and genuine native route/review evidence through existing adopted commands before product writes. No new review backend or old review25/namespace retry.
  - Candidate authoring/planlib behavior runs only in isolated regression fixtures until exact-target independent clearance, unchanged focused/full validation and formal publication. Never use candidate controls to activate themselves or plan387. Keep all original service/access stops, consumption and missing evidence.
  - PR20 may carry the bounded contract repair and plan387 regeneration, with its title/body rewritten around the final diff and final-SHA CI checked after an authorized normal push. No PR20 merge, main/dev direct write, force push, release or additional PR is required or authorized.
checked_summary_ja: 未開始backlogの検証方法の未定を保持し、実装開始と受入を拒否する。

## Decisions

- Reuse the owner-approved scope from parent-provided proposal Sentinel_9edaa417f6508191823dcf458ca29153 and approval Sentinel_fea8b46d18a881918c6d4a485c49bcb4 at 2026-10-11 02:12 UTC. The owner's words authorize this bounded implementation; they do not authorize deletion or continuation through successors.
- Treat verification definitions and actual successful evidence separately. A reason records why an acceptance item's future verification is not designed; it is neither a witness command nor a success. Keep genuine acquisition/live integration unresolved and all whole E1-E5 acceptance unmet.
- Extend the existing structured authoring and canonical manifest validation only. Keep pending entries explicit and digest-bound, require reasons, reject mixed conflicting definitions, and refuse any pending entry at active/start/completion boundaries before effects. Do not weaken complete witness coverage for an executable plan.
- Keep the new representation conditional so fully assigned root/generated inputs and existing generated legacy argument output retain their bytes. Preserve readable historical backlog bytes without manufacturing reasons or success for them. Mirror the policy and authoring module in this exact change.
- Retain plan387's original requirements, acceptance and completion conditions, source-order digests, declared product scope, four independent fixture predicates and every safety restriction. Move its appendix clauses into Decisions, Tasks and Validation Notes through one complete checked input, retained as a repository source JSON for future regeneration.
- This contract repair is separate from plan389 and from E1-E5 product implementation. Plan389's provisional commit, worktree, branch and backup stay unchanged. No old445/446 ledger reconstruction, budget reset, PR1 candidate import/adoption or refusal bypass.

## Tasks

- [ ] After exact plan publication and adopted execution admission, add bounded unassigned-reason support to structured backlog input and derive the digest-bound manifest representation through the existing renderer. Define any necessary field names from their concrete referents first.
- [ ] At canonical manifest and lifecycle entrypoints, reject malformed reasons and pending verification at active authoring, promotion, start and acceptance before any effect. Cover fully assigned, mixed and wholly unassigned backlog inputs without changing existing mapped validation authority.
- [ ] Regenerate the complete plan387 from its checked repository source input using only supported sections. Preserve all original whole E1-E5 strings/digests, fixture clauses and safety holds; no witness or test name is invented to satisfy the checker.
- [ ] Review the exact diff and invariants, run the registered focused regression suite, obtain adopted native independent exact-target clearance and run unchanged lint/smoke once in this implementation task's own locked environment. Record any formal failure through the existing diagnosis process.
- [ ] Keep product acceptance closed until every declared condition has actual required evidence. Finish only through the authorized exact publication procedure; then normal-push only the existing PR20 source, update its description/reply accurately and inspect CI for that exact published head. If deletion remains unauthorized, retain the clean commit and verified bundle without pushing an alternate publication path.

## Validation Notes

- Owner quotation received through the parent: 提案の方針で進めて良い。. No separate source read, reply linkage, original chat identifier or platform signature is claimed. No standing continuation authorization is inferred.
- Source and PR20 head were freshly rechecked as ba8657ba3b1e52013392f3c148008a5cca1f5bb3. Parent names this child as the sole writer. The source is clean; local dev's unadopted81 commits are excluded. Earlier f254ae2036d5e08f02a8bc3165cc4656c1c1a89f remains PR20's published dev base.
- Tier2 is conservative because this repair changes the preparation/lifecycle representation contract, while execution, review, safety and validation authority must remain unchanged. The nine exact paths form one bounded preservation invariant; no additional quality-assurance mechanism or unrelated scope is authorized.
- Existing root fixture median-root-active is accepted by build_document without executing witnesses; only authoritative validation command syntax is allowlisted. The observed missing-witness CLI failure concerns an unresolved design, not absence of a past passing result. Existing offline state tests cannot prove genuine approval acquisition or actual quality review.
- The product focused command and regression cases are future validation definitions only; none has run for this implementation. Direct-task plan authoring lint/smoke results validate preparation and do not satisfy this plan's product acceptance or E1-E5.
- The ordinary publisher journals source fast-forward, evidence relocation and exact task worktree/branch cleanup. Its retain exception is only for a completed numbered replan transition, not this authoring task. Hold at this boundary until the exact new targets are authorized; do not manually update refs, remotely publish a provisional active plan or reuse plan389's deletion approval.
- Full external transcript and hook evidence are not collected for this authoring phase. Reuse existing known hook support and approvals without pretending they are this implementation's fresh execution-bound route or quality receipt.
