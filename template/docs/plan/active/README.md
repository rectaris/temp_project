# active の使い方

このディレクトリには、実行中の計画と、着手後に条件解決まで延期した計画を置きます。

## 基本方針

- 実行中の計画の一覧は `docs/plan/plan.md` が持ちます。このディレクトリを走査して一覧を作り直さないでください。
- まだ着手しない作業候補は `docs/plan/backlog/` に置きます。
- backlog から着手するときは `.project-agent-workflow/scripts/promote-plan.sh` で active へ移します。
- 完了した計画は `.project-agent-workflow/scripts/complete-plan.sh` で条件を確認してから `.project-agent-workflow/scripts/finalize-active-plan.sh` で `docs/plan/checked/` へ移します。
- 番号は active、backlog、checked で共通の連番として扱います。

## このファイルがある理由

Git は空のディレクトリを追跡しません。この README がないと、最後の計画を `checked` へ移した時点で `active/` が消え、次に計画を作るたびに作り直されます。`docs/plan/README.md` も規定も `docs/plan/active/` を常設の置き場として説明しているため、あるときと無いときが混在すると、読む側が毎回「無いことに意味があるのか」を確かめ直すことになります。

このファイルは計画ではありません。計画を選ぶ処理はすべて `[0-9][0-9][0-9]-*.md` で絞るため、`docs/plan/backlog/README.md` と同じく走査の対象外です。

計画が実行中かどうかは、このディレクトリの有無では判定しません。`docs/plan/plan.md` の内容だけで決まります。

このファイルはテンプレートが配るものです。削除しても次の `copier update` で戻ります。`active/` を常設にすることがこのファイルの目的であるため、その復帰は意図した動作です。

## AI エージェント向け情報

詳しい運用ルールは `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` を参照してください。
