# Keep docs/plan/active present instead of creating and deleting it around every plan

status: checked
primary_invariant: docs/plan/active/ is present in a fresh checkout of this repository and of a generated project, whether or not a plan is open.
task_types:
  - planning_docs
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: ordinary
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"git ls-files lists no path under docs/plan/active/ in this repository and none under template/docs/plan/active/, while docs/plan/backlog/, docs/plan/shelved/, docs/plan/handoffs/ and template/docs/plan/{backlog,shelved,handoffs}/ each carry a tracked README.md. Git tracks no empty directory, so the directory exists only between plan creation and finalization.","kind":"reproduced_defect"}
  - {"evidence":"template/docs/plan/shelved/README.md was added on 2026-08-30, after the 2026-08-09 commit 62ceb88 removed template/docs/plan/{active,backlog,checked,handoffs}/.gitkeep, so a documentation file is the accepted way to ship a plan lifecycle directory and an empty .gitkeep is the rejected one.","kind":"existing_mechanism"}
  - {"evidence":"Every consumer of the directory selects files with the glob [0-9][0-9][0-9]-*.md, and no check restricts what else the directory may contain, so a README.md is invisible to plan selection exactly as docs/plan/backlog/README.md already is.","kind":"mechanical_transformation"}
completion_conditions:
  - docs/plan/active/ holds a tracked file in this repository, so the directory survives finalization of the last open plan.
  - A project generated from the template carries docs/plan/active/ with no plan open, and its validation passes.
completion_witness_map:
  - {"condition_sha256":"sha256:88bb86a77539b109a46afa876d79f7fb1442f456a4333ac3e07bfd3183adaaed","witness":"python3 scripts/check-root-agent-policy.py"}
  - {"condition_sha256":"sha256:3c5aaf1807613a97b221c479790e692c299f389bd54a363747326bec601b52af","witness":"tests/smoke.sh"}
write_scope:
  - docs/plan/active/README.md
  - scripts/project_workflow/copier_inventory.py
  - template/docs/plan/active/README.md
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - template/docs/plan/backlog/README.md
  - template/docs/plan/shelved/README.md
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
focused_validation:
  - python3 scripts/check-root-agent-policy.py
  - tests/smoke.sh
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - docs/plan/active/ is present in a fresh checkout of this repository and of a generated project whether or not a plan is open, and nothing selects the file that keeps it there as a plan.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:073899a14bb12aa06a42d1d83b2908ce5ab793c51e480d961ff2545979ff9184","stage":"focused","witness":"tests/smoke.sh"}
checked_summary_ja: 計画のたびに作り直される docs/plan/active を常設にする

## Decisions

- Keep the directory with a README.md rather than a .gitkeep, because commit 62ceb88 removed the .gitkeep placeholders under template/docs/plan/ and the CHANGELOG records that a deleted one must not return, while README.md placeholders for the sibling directories were kept and a new one was added afterwards.
- Write the root file and the template file separately instead of mirroring one text, because this repository creates plans with scripts/create-root-plan.py and ships no promote-plan.sh, while a generated project uses .project-agent-workflow/scripts/promote-plan.sh, and the root docs/plan/backlog/README.md is already a repository-specific record rather than a copy of the template one.
- Register the new template file in scripts/project_workflow/copier_inventory.py, because check-copier-template.py compares that manifest against every tracked file under template/ and refuses an unlisted one; this records the file as deliberate rather than widening any authority.
- Do not list the open plans in the new file, because docs/plan/plan.md is the index every enforcing command parses and a second list would go stale without any check observing it.

## Tasks

- [x] Add docs/plan/active/README.md describing this repository's active plan location and why the directory is kept.
- [x] Add template/docs/plan/active/README.md describing the same location for a generated project, using the managed script paths.

## Validation Notes

検証結果:

- `python3 scripts/check-root-agent-policy.py` — 通過。`docs/plan/active/` を走査する経路が新しい `README.md` を計画として選ばないことを確認した。
- `scripts/lint-project-workflow.sh` — 通過。`check-copier-template.py` のテンプレート目録検査が、新しいテンプレートファイルの登録漏れを実際に検出したため、`scripts/project_workflow/copier_inventory.py` へ登録した。
- `tests/smoke.sh` — 通過。テンプレートから生成したプロジェクトが `docs/plan/active/README.md` を持ち、その状態で生成側の検証が通ることを確認した。

事前調査で確かめた事実:

- `v1.4.5` から生成したプロジェクトには `docs/plan/active/` が存在しなかった。`backlog`、`handoffs`、`shelved` は `README.md` によって存在していた。
- 生成先が削除したテンプレート由来のファイルは、次の `copier update` で復帰する。`docs/plan/backlog/README.md` を削除した生成先を `v1.4.5` から `v1.4.6` へ更新して実地に確認した。この性質は `active/` を常設にする目的と一致するため、テンプレート側の `README.md` にその旨を明記した。当初「削除したものは戻らない」と書いていたが、この確認により誤りであることが判明したので書き直した。
- 置き場の保持に `.gitkeep` を使わなかったのは、commit `62ceb88` が `template/docs/plan/` 配下の `.gitkeep` を削除し、CHANGELOG が「生成先が削除した `.gitkeep` を通常の update で再生成しない」と記録している一方、兄弟ディレクトリの `README.md` は残され、`shelved/README.md` はその後に追加されているためである。

独立レビューは受けていない。Tier 1 の文書追加であり、製品の挙動、検証権限、安全境界のいずれも変更していない。
