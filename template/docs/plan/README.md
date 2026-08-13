# docs/plan の使い方

このディレクトリは、作業中の計画、後で扱う候補、引き継ぎ用の一時メモ、完了記録を分けて管理する場所です。

## 主なファイル

- `plan.md`: 実行中または着手後に延期した未解決の作業だけを載せる短い索引です。
- `active/*.md`: 実行中または着手後に条件解決まで延期した、未解決の作業計画です。
  対象ファイル、制約、検証方法、完了条件を書きます。
- `backlog/*.md`: まだ着手しない候補や、条件待ちの作業を置きます。
- `checked.md`: 完了済み記録を機械的に参照するための索引です。
- `checked/YYYY/MM/01-15/*.md`: 月前半に完了した作業の詳細記録です。
- `checked/YYYY/MM/16-31/*.md`: 月後半に完了した作業の詳細記録です。
- `replanned.md`: 要件を保持して再構成した計画の索引です。
- `replanned/YYYY/MM/01-15/*.md` と `replanned/YYYY/MM/16-31/*.md`: 完了とは区別された再構成履歴です。
- `replanned/contracts/`: 元要件と後続計画の対応を保持する機械可読契約です。
- `handoffs/`: 複数エージェントや別セッションへ渡す一時的な作業依頼を置きます。

## 運用の考え方

- `plan.md` には、実行中の作業と、着手後に延期理由を記録して未解決のまま保持する作業だけを載せます。
- 先送りの候補や監視項目は `backlog/` に置きます。
- 完了した作業は完了日に応じて `checked/YYYY/MM/01-15/` または `checked/YYYY/MM/16-31/` に移して、`checked.md` の索引へ記録します。
- 完了済み記録は過去の作業履歴です。
- 再構成済み記録は完了記録ではありません。元の受入れ条件は後続計画と統合計画へ引き継ぎます。
  現在の仕様確認では、最新の `docs/agent/` 仕様や実装ファイルを優先します。
- `replan_required` の計画を再構成するときは、親が固定 JSON 契約を作成し、`.project-agent-workflow/scripts/restructure-plan.py <specification.json>` を実行します。

## AI エージェント向け情報

AI エージェント向けの詳細な計画運用ルールは、`.project-agent-workflow/docs/agent/SPEC_PLAN_WORKFLOW.md` にあります。

この README は人間向けの概要です。
作業ルーティングや検証ルールの正確な判断には、`.project-agent-workflow/docs/agent/spec-index.yaml` と `docs/agent/SPEC_*.md` を参照してください。
