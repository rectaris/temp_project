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
