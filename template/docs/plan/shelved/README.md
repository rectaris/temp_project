# shelved の使い方

このディレクトリには、**実装しないと判断した plan** を置きます。優先度が低いだけの作業は `docs/plan/backlog/` に残します。

## backlog との違い

- `backlog` は「まだ着手していない」状態です。いずれ実施します。
- `shelved` は「実施しないと決めた」状態です。判断そのものを記録します。

判断を記録せずに放置すると、なぜ止まっているのか誰にも再構成できない置き場になります。そのため shelved の plan には次の 2 つのフィールドが必須です。

- `shelved_reason`: 実装しないと判断した理由
- `shelved_at`: 判断した日付 (`YYYY-MM-DD`)

いずれかが欠けている、または空である場合は plan 検証が失敗します。

## 誰が決めるか

見送りはオーナーの判断です。エージェントは見送り候補と根拠を提示するところまでで、自分の判断で移動してはいけません。backlog を短くするための移動も認められません。

`shelved_reason` には「誰の指示によるか」を書いてください。後から読む人が、オーナーの決定なのかエージェントの推測なのかを区別できるようにするためです。

## 移動のしかた

```sh
.project-agent-workflow/scripts/shelve-plan.sh docs/plan/backlog/NNN-slug.md '理由'
```

## 判断を戻すとき

見送りは終端状態ではありません。次の 2 経路で戻せます。

```sh
.project-agent-workflow/scripts/shelve-plan.sh --restore docs/plan/shelved/NNN-slug.md
.project-agent-workflow/scripts/promote-plan.sh docs/plan/shelved/NNN-slug.md
```

前者は backlog へ、後者は active へ戻します。

## 見送りは他の plan を止めません

見送った plan は前提条件として数えません。`integration_gates` や依存関係の記述が見送り済みの plan を指していても、依存側の plan は着手できます。実施しないと決めた plan を前提のまま残すと、見送りが無関係な作業を止めてしまうためです。

gate の文面は書き換えないでください。gate は履歴です。代わりに、依存側の plan の Validation Notes に「どの plan を前提から外したか」と「それによって省略される確認は何か」を着手前に記録します。

見送りを取り消して plan を戻した場合、その前提は再び有効になります。

## 要求は削除されません

shelved の plan はファイルとして残り、replan 契約からも解決できます。見送りは要求の削除ではなく、実施時期の判断です。

## AI エージェント向け情報

詳しい運用ルールは `.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` を参照してください。
