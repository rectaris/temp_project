# Derive plan overview rows from existing lifecycle files

status: backlog
primary_invariant: A read-only overview derives displayed plan status and links from one unambiguous existing lifecycle document, preserving human priorities without granting activation or completion authority.
task_types:
  - template_workflow
  - planning_docs
  - security
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 2
implementation_risk: ordinary
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"The backlog README lists eight unstarted plans and old backlog links to 272, 281 and 282, whose documents now exist only under checked.","kind":"existing_mechanism"}
  - {"evidence":"Existing plan-authoring and planlib parsers already interpret manifests and the canonical active index; root wrappers already load template-owned implementations.","kind":"existing_mechanism"}
completion_conditions:
  - The default report lists current backlog documents; a bounded explicit id set resolves actual active, backlog, checked, replanned and shelved status and paths.
  - Duplicate ids, index/file disagreements, missing requested records and unsafe source paths fail with bounded diagnostics; an empty backlog is a valid explicit result.
  - The report writes only to stdout, escapes document text, leaves source bytes unchanged and creates no second registry of approvals or priorities.
  - Root and generated entrypoints share one implementation, and Markdown links resolve relative to an explicit report location.
completion_witness_map:
  - {"condition_sha256":"sha256:af95c8dbf16aaec689d175e38743a7b0b46cd5a2c975d3a5954192f149e150fa","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:a74c5528cbfe2e0d5f5b4cea48e1180aafe0c607f125a4e955eb919a07b663bf","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:dd1dca61b9a1cccdf10d4c21d6898e40aa65e2a65cab4609785a82e637b4990f","witness":"python3 tests/test-validation-tools.py"}
  - {"condition_sha256":"sha256:086558ee7929d9a2ff530f6a7465fba0ae48e93aea484668670603d598a8fd23","witness":"python3 scripts/check-copier-template.py"}
write_scope:
  - scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/render-plan-overview.py
  - template/.project-agent-workflow/scripts/plan_overview.py
  - scripts/project_workflow/copier_inventory.py
  - scripts/check-copier-template.py
  - tests/validation_tools/plan.py
  - tests/test-validation-tools.py
  - docs/plan/backlog/README.md
  - template/docs/plan/backlog/README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - docs/agent/spec-index.yaml
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - scripts/project_workflow/plan_authoring.py
  - template/.project-agent-workflow/scripts/planlib.py
  - docs/plan/checked/2026/09/01-15/282-render-plans-from-checked-authoring-input.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 tests/test-validation-tools.py
  - python3 scripts/check-copier-template.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The default report lists current backlog documents; a bounded explicit id set resolves actual active, backlog, checked, replanned and shelved status and paths.
  - Duplicate ids, index/file disagreements, missing requested records and unsafe source paths fail with bounded diagnostics; an empty backlog is a valid explicit result.
  - The report writes only to stdout, escapes document text, leaves source bytes unchanged and creates no second registry of approvals or priorities.
  - Root and generated entrypoints share one implementation, and Markdown links resolve relative to an explicit report location.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:af95c8dbf16aaec689d175e38743a7b0b46cd5a2c975d3a5954192f149e150fa","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:a74c5528cbfe2e0d5f5b4cea48e1180aafe0c607f125a4e955eb919a07b663bf","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:dd1dca61b9a1cccdf10d4c21d6898e40aa65e2a65cab4609785a82e637b4990f","stage":"focused","witness":"python3 tests/test-validation-tools.py"}
  - {"acceptance_sha256":"sha256:086558ee7929d9a2ff530f6a7465fba0ae48e93aea484668670603d598a8fd23","stage":"focused","witness":"python3 scripts/check-copier-template.py"}
integration_gates:
  - Start only after this backlog plan is selected for implementation and published as active; use its exact bound task worktree.
  - Use bounded parent implementation and independent read-only review. Keep existing correction and review limits, mandatory validation, Copier preservation and external-effect authority.
  - Use checked Plan 282 infrastructure; do not recreate plan authoring or change its schemas.
  - Resolve at most 128 requested ids, bound output, and confine discovery to the selected repository rather than home or arbitrary worktrees.
checked_summary_ja: プランの状態と場所から一覧を生成し、古いリンクと未着手表記を残さない。

## Decisions

- Add a stdout-only command using existing manifest and active-index parsers. Add no authoring format, mutable catalog or automatic lifecycle updater.
- Keep purpose, priority, dependencies and owner choices human-authored. Derive only identifier, status and path rows.
- Default to backlog; an explicit historical id set preserves the distinct meanings of checked, replanned and shelved.
- Require --relative-to for Markdown links and support bounded JSON output; do not infer approval or dependency readiness.
- Keep this display optional. Stale explanatory Markdown must not become a new commit, completion or implementation gate.

## Tasks

- [ ] Add fixtures for current backlog, checked former backlog, replanned/shelved records, empty sets, duplicate ids and stale index rows.
- [ ] Implement shared discovery, resolution and rendering with bounded input/output and root/generated entrypoints.
- [ ] Test ordering, relative links, escaping, unsafe inputs and identical source bytes after reports.
- [ ] Document generation while retaining human narrative; refresh the current overview once as an example.
- [ ] Run focused validation, independent review and the mandatory suite.

## Validation Notes

- Planning baseline: b3e300888412f7e9c2fb243435da4cb4082f5135 in temp_project.
- Owner instruction: 提案の方針でプランを作成せよ。変更点が多い場合は複数のプランとして作成せよ。手続きとして削減するべき部分をまとめたり、スキル化、関数化するべき部分など、改善できる部分をまとめよ。
- This instruction authorizes plan authoring, not implementation or reopening a stopped run. This is ordinary backlog work, not a reconstruction successor.
- See docs/plan/backlog/README.md for procedure reductions, existing-plan reuse and implementation order. Full decision audit stays in local development-process-planning evidence.
- The shared authoring checker derives correspondence and digests; the parent reviews witness semantics. No measured productivity saving is claimed.
