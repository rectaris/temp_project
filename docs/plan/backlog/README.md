# 開発手続きの改善プラン

2026年9月12日に、現行コードで再現した三件の問題を実装プランとして追加した。
[調査結果と根拠](../development-improvements-20260912.md)に、以前の改善を再利用する範囲と今回の完了条件をまとめている。
三件とも未着手であり、実装開始を指示されたものを公開済みの状態から一件ずつactiveへ昇格する。

## 実行順

[311](311-use-current-files-for-smoke-rendering.md)で、生成テストが現在のファイルを取りこぼさないようにする。
その後、[310](310-reuse-canonical-index-parser-in-overviews.md)で、プラン一覧の表示と実行前検査が同じ解析規則を使うようにする。
続けて[312](312-check-root-archive-index-targets.md)で、完了記録の索引が実在する保存先を指すことをrootでも検査する。
この順序は優先順位であり、310と312の必須の前提条件ではない。
テストの登録先や変更対象を共有するため、並列には実装しない。

以前ここに記載していた九件は、現在の未着手一覧から外した。
完了または再構成の履歴は[checkedの一覧](../checked.md)と[replannedの一覧](../replanned.md)で確認できる。
表示の更新は任意の文書整理であり、新しいコミット条件や実装の停止条件にはしない。

## 現在のbacklog一覧

次の一覧は`python3 scripts/render-plan-overview.py --relative-to docs/plan/backlog/README.md`で生成した。

| id | status | title | path |
| --- | --- | --- | --- |
| [310](310-reuse-canonical-index-parser-in-overviews.md) | backlog | Use the canonical active-index parser in read-only plan overviews | docs/plan/backlog/310-reuse-canonical-index-parser-in-overviews.md |
| [311](311-use-current-files-for-smoke-rendering.md) | backlog | Use the selected current files for every generated-project smoke copy | docs/plan/backlog/311-use-current-files-for-smoke-rendering.md |
| [312](312-check-root-archive-index-targets.md) | backlog | Validate root checked-index targets through the shared archive check | docs/plan/backlog/312-check-root-archive-index-targets.md |
