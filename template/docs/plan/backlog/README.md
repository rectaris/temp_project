# backlog の使い方

このディレクトリには、今すぐ着手しない作業候補や、条件待ちの作業を置きます。

## 基本方針

- 現在進行中の作業は `docs/plan/active/` に置きます。
- backlog は、開始条件、対象ファイル、検証方法、完了条件が見える形で保存します。
- 着手するときは `.project-agent-workflow/scripts/promote-plan.sh` で active に移します。
- backlog から active へ昇格する計画は、`plan_purpose`、`feasibility_evidence`、`completion_conditions`、`completion_witness_map` を満たす必要があります。
  条件を満たさない古い計画は、後続計画を作らずに、その計画自身を書き直してから昇格します。
- 番号は active、backlog、checked で共通の連番として扱います。

## AI エージェント向け情報

詳しい運用ルールは `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` を参照してください。

## 現在の backlog 一覧

`python3 scripts/render-plan-overview.py --relative-to docs/plan/backlog/README.md` で生成した一覧。

| id | status | title | path |
| --- | --- | --- | --- |
| [273](273-stop-indivisible-tier-one-work-without-descope.md) | backlog | Stop indivisible Tier 1 work without an impossible descope | docs/plan/backlog/273-stop-indivisible-tier-one-work-without-descope.md |
| [274](274-preserve-project-owned-agent-model-settings.md) | backlog | Preserve project-owned agent model settings during Copier updates | docs/plan/backlog/274-preserve-project-owned-agent-model-settings.md |
| [275](275-route-detailed-agent-policy-on-demand.md) | backlog | Route detailed agent policy without losing mandatory requirements | docs/plan/backlog/275-route-detailed-agent-policy-on-demand.md |
| [276](276-run-bounded-parent-owned-candidate-preflight.md) | backlog | Run one bounded parent-owned preflight per candidate | docs/plan/backlog/276-run-bounded-parent-owned-candidate-preflight.md |
| [299](299-reuse-established-decisions-in-existing-skills.md) | backlog | Reuse established decisions through existing planning skills | docs/plan/backlog/299-reuse-established-decisions-in-existing-skills.md |
| [300](300-compose-parent-direct-execution-preparation.md) | backlog | Compose existing parent-direct execution preparation | docs/plan/backlog/300-compose-parent-direct-execution-preparation.md |
