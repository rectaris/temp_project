# 開発手続きの改善プラン

2026年9月12日に、現行コードで再現した三件の問題を実装プランとして追加した。
[調査結果と根拠](../development-improvements-20260912.md)に、以前の改善を再利用する範囲と今回の完了条件をまとめている。
四件とも完了済みである。
実装開始を指示されたものを、公開済みの状態から一件ずつactiveへ昇格する。

## 実行順

[311](../checked/2026/09/01-15/311-use-current-files-for-smoke-rendering.md)は完了し、生成テストが現在のファイルを取りこぼさなくなった。
[310](../checked/2026/09/01-15/310-reuse-canonical-index-parser-in-overviews.md)も完了し、プラン一覧の表示と実行前検査が同じ解析規則を使うようになった。
[312](../checked/2026/09/01-15/312-check-root-archive-index-targets.md)は権威的検証で`restructure-plan.py`の版差判定と衝突していったん停止したが、313の修復後に新しい実行で完了し、完了記録の索引が実在する保存先を指すことをrootでも検査するようになった。
[313](../checked/2026/09/01-15/313-read-activation-archives-of-every-vintage.md)はその修復で、起動参照が旧版の完了記録も読めるようになった。
この依存は312の再開条件であり、他の順序は優先順位にすぎなかった。
テストの登録先や変更対象を共有するため、並列には実装しなかった。

以前ここに記載していた九件は、現在の未着手一覧から外した。
完了または再構成の履歴は[checkedの一覧](../checked.md)と[replannedの一覧](../replanned.md)で確認できる。
表示の更新は任意の文書整理であり、新しいコミット条件や実装の停止条件にはしない。

## 現在のbacklog一覧

次の一覧は`python3 scripts/render-plan-overview.py --relative-to docs/plan/backlog/README.md`で生成した。

| id | status | title | path |
| --- | --- | --- | --- |
| [320](320-pin-optional-harness-instructions.md) | backlog | Pin optional instruction revisions and retain a measured adoption path | docs/plan/backlog/320-pin-optional-harness-instructions.md |
| [322](322-record-downstream-template-improvements.md) | backlog | Record template improvement evidence in generated repositories | docs/plan/backlog/322-record-downstream-template-improvements.md |
| [323](323-collect-template-improvement-requirements.md) | backlog | Collect local feedback as traceable template requirement candidates | docs/plan/backlog/323-collect-template-improvement-requirements.md |
| [324](324-derive-development-direction-from-accepted-requirements.md) | backlog | Render development direction from explicitly adopted requirements | docs/plan/backlog/324-derive-development-direction-from-accepted-requirements.md |

## ハーネスのモデル更新への対応

[比較ツールのプラン](../active/319-compare-harness-runs-locally.md)の完了後に、[補助指示の版選択のプラン](320-pin-optional-harness-instructions.md)を開始する。
共通の要件と権限を保ち、比較記録に基づいて補助指示の採用を判断できるようにする。
両プランの完了は、実モデルでの性能改善を確認したことを意味しない。
