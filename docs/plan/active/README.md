# active の使い方

このディレクトリには、実行中の計画と、着手後に条件解決まで延期した計画を置きます。

## 基本方針

- 実行中の計画の一覧は `docs/plan/plan.md` が持ちます。このディレクトリを走査して一覧を作り直さないでください。
- まだ着手しない作業候補は `docs/plan/backlog/` に置きます。
- 新しい計画は `scripts/create-root-plan.py` で作ります。番号は active、backlog、checked、replanned、shelved で共通の連番です。
- 完了した計画は `scripts/complete-plan.sh` で条件を確認してから `scripts/finalize-active-plan.sh` で `docs/plan/checked/` へ移します。
- 実行中の計画は既定で1件です。複数を同時に進めるには `docs/plan/execution-groups/` の記述が要ります。

## このファイルがある理由

Git は空のディレクトリを追跡しません。この README がないと、最後の計画を `checked` へ移した時点で `active/` が消え、次に計画を作るたびに作り直されます。手順書も規定も `docs/plan/active/` を常設の置き場として書いているため、あるときと無いときが混在すると、読む側が毎回「無いことに意味があるのか」を確かめ直すことになります。

このファイルは計画ではありません。計画を選ぶ処理はすべて `[0-9][0-9][0-9]-*.md` で絞るため、`docs/plan/backlog/README.md` と同じく走査の対象外です。

計画が実行中かどうかは、このディレクトリの有無では判定しません。`docs/plan/plan.md` の内容だけで決まります。

## AI エージェント向け情報

詳しい運用ルールは `docs/agent/SPEC_PLAN_WORKFLOW.md` を参照してください。
