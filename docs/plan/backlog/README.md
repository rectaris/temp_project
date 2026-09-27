# 未着手プランの一覧

このディレクトリには、作成済みで実装に未着手のプランを置く。
実行中のプランは`docs/plan/plan.md`が持ち、このディレクトリの走査では決まらない。
実装を指示されたものを、一件ずつactiveへ昇格する。

このファイルはプランではない。
プランを選ぶ処理は`[0-9][0-9][0-9]-*.md`で絞るため、この README は走査の対象外である。

## 実装前の精査

2026-09-26 に、ここにあるプランをすべて現行のコードと照合した。
書き込み範囲の不足、許可されていない検証コマンド、古くなった前提、独立した機能の抱き合わせを、どのプランも一つ以上抱えていた。
各プランは同じ受け入れ条件を保ったまま、範囲、実装方法、検証方法を書き直してある。
書き直した理由は、各プランの Validation Notes の先頭に残している。

## Pythonの静的チェック

Ruffによる検査を入れた[353](../checked/2026/09/16-31/353-enforce-bounded-python-lint.md)は完了している。
残りの2件は同じ検証の配線を書き換えるため、次の順に一件ずつ実装する。

1. [366：検証用スクリプトの整形](366-format-initial-python-validation-tools.md)
   353のRuffをそのまま使い、6ファイルを整形して、整形漏れをローカルとCIで検査する。
   複数のスクリプトで同一に保つ文法ブロックは、整形の対象から外す。
2. [365：検証用スクリプトの型検査](365-check-types-in-python-validation-tools.md)
   npm版のPyright 1.1.407をNode 24で導入し、同じ6ファイルの型を検査する。
   Pyrightは隠しディレクトリの下のファイルを解析しないため、配置ごとに設定ファイルを分ける。

## 開発環境と進め方の規則の変更

オーナーの指示で、2026-09-26 に見つかった開発環境と進め方の問題を、規則として定める5件を作った。2026-09-27 に1件を加えた。
Issue #15の4件より先に、次の順に一件ずつ、それぞれ新しい会話セッションで実装する。

1. [419：プランの行き先ごとに一つの番号予約](419-keep-one-plan-id-reservation-per-authoring-target.md)
   下書きを直して確認し直しても、プラン番号が飛ばないようにする。
2. [420：プランの開始時に一度だけ与える続行の承認](420-record-standing-owner-continuation-up-to-four-reviews.md)
   オーナーが開始時に承認すれば、4回目のレビューまでは続行の承認を求めない。4回目の後の判断は、必ずオーナーが行う。
3. [421：提供が終了したSparkからTerraへの置き換え](421-route-writable-work-to-terra-after-spark-retirement.md)
   OpenAIは[2026-09-14にgpt-5.3-codex-sparkの提供を終了した](https://learn.chatgpt.com/docs/changelog#codex-2026-09-14-codex-spark-deprecation)。書き込みの作業はgpt-5.6-terraのmediumに統一し、生成先のプロジェクトでも更新時に置き換える。
4. [424：計画ファイルに記録したオーナーの承認での続行](424-take-standing-authorization-from-the-plan-manifest.md)
   オーナーの承認の言葉を計画ファイルの`standing_continuation_authorization`に記録しておけば、レビューで止まるたびに承認を求めずに、4回目のレビューまで続行する。421で開始時の記録を作らず承認を2回求めたため、2026-09-27に追加した。422と423にもこの承認を記録するので、422より先に実装する。
5. [422：タスクのworktreeへのuv環境の用意](422-provision-task-worktrees-with-the-locked-uv-environment.md)
   新しいworktreeを作るときに`uv sync --locked`で`.venv`を作り、ルートの検証をその環境で実行する。
6. [423：サンドボックスから見えるPythonでの補助処理](423-run-sandboxed-python-helpers-from-a-reachable-interpreter.md)
   ランナーをuvの仮想環境で動かしても、サンドボックスの中のPythonが動くようにする。422の完了後に始める。

423が完了するまでは、`tests/test-sandboxed-plan-worker.py`をシステムの`python3`で実行する。

## Issue #15の最小の評価実行

[Issue #15](https://github.com/rectaris/temp_project/issues/15)のPhase 1のうち、同じCodexの構成を2回実行して既存の`compare-harness-runs.py`で比べ、結果が再現されることを示すまでを、4件に分けた。
評価のツールはこのリポジトリ専用で、テンプレートには入れない。
実験の記録は`.agent-artifacts/evaluations/<experiment-id>/`に置く。

次の順に一件ずつ、それぞれ新しい会話セッションで実装する。
番号は作成順に割り当てたため、418が417より先になる。

1. [415：違う次元の集合による実行構成の比較](415-compare-named-run-configurations-by-changed-dimensions.md)
   比較形式にschema 2を加え、同じ構成どうしの比較を`replication`として報告する。schema 1の比較は変えない。
2. [416：実行前に確定する評価の定義](416-freeze-evaluation-experiments-before-execution.md)
3. [418：分離したCodexのサンドボックスでの実行](418-execute-evaluation-runs-in-isolated-codex-sandboxes.md)
4. [417：独立した検証と比較](417-verify-evaluation-runs-and-compare-observations.md)

4件の完了後、番号付きのプランの外で、実モデルを使って同じ構成どうしの比較を1回行う。
Codexの利用枠を消費し、その結果は再現性の確認であって、構成を採用する根拠にはならない。

## 能力と実装の境界によるOpenCode Goへの委任

親のオーケストレーターから別のCLIへ作業を渡す経路を、[Issue #14](https://github.com/rectaris/temp_project/issues/14)の能力と実装の境界に載せて、読み取り専用から順に広げる。
前提の資格情報隔離は、355を再構成した[359](../checked/2026/09/01-15/359-isolate-opencode-go-inference-credentials.md)として完了済みである。

元の356と357から分けた394から399は、Issue #14のオーナーの指示で正規の再構成をもう一度行い、404から409に1件ずつ置き換えた。
元の本文と受け入れ条件は[replannedの一覧](../replanned.md)から辿れる。
後継では、親はOpenCodeを名指しせず能力の名前で要求し、Capability Registryが既定のCodexか、プロジェクトが明示的に有効にしたOpenCode Goの実装を選ぶ。
OpenCode固有の起動方法と資格情報の中継は、OpenCodeGoBackendの中に閉じる。

後継の6件は、次の前提作業を integration_gates の文章で待つ。

- Issue #14の基盤は、[410](../checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md)として完了した。Capability RegistryとWorkerBackend境界を追加し、現行のCodexの経路をCodexBackendとして動作を変えずに包んでいる。後継が編集する`docs/agent/capability-registry.json`と`scripts/project_workflow/worker_backends.py`、およびそれぞれのテンプレートの写しは、この名前で作られた。登録表はworker_backends.pyの固定の対応表と一致する必要があるため、実装を加える後継は両方を同時に変える。
- [Issue #15](https://github.com/rectaris/temp_project/issues/15)の最小の評価実行は、404の開始前に完了させる。
- 408は、#15でCodexとOpenCode Goの読み取り専用の動作を比べた結果が、書き込みの実装を有効にすることを支持するまで開始しない。

次の順に一件ずつ実装する。

1. [410：Issue #14の基盤](../checked/2026/09/16-31/410-resolve-codex-runner-through-capability-registry.md)（完了）
2. Issue #15の最小の評価実行（前の節の415、416、418、417と、実モデルでの再現性の確認）
3. [404：読み取り専用の能力を処理するOpenCode Goの実装](404-run-read-only-capabilities-through-opencode-go-backend.md)
4. [405：どの能力も有効にしない実装の設定](405-seed-disabled-opencode-go-backend-configuration.md)
5. [406：能力による発見とCopierの配布](406-discover-read-only-capabilities-through-registry.md)
   元の399の受け入れ条件をすべて引き継ぎ、3件をまとめて検証する。
6. [407：WorkerBackendを通じた試行ごとの起動情報](407-bind-worker-backend-dispatch-provenance.md)
   前提は基盤だけで、OpenCodeを名指ししない。
7. Issue #15による読み取り専用の動作の比較
8. [408：Codex以外で最初の書き込みの実装](408-add-opencode-go-writable-backend.md)
9. [409：書き込みの能力の発見とCopierの配布](409-discover-plan-implementation-backends-through-registry.md)
   元の396の受け入れ条件をすべて引き継ぎ、3件をまとめて検証する。

OpenCode Goは`plan_implementation`だけに登録し、`bounded_implementation`はCodexの既存の設定に残す。
`bounded_implementation`にはサンドボックスを通る実装候補の経路がないためである。
どの完了も、実際のモデルで品質が向上したことを意味しない。

## 別セッションでの並列実装

[並列実装の計画](../parallel-session-development-20260926.md)に、実装担当2セッションと統合担当1セッションの分担、実施順序、完了条件をまとめた。

1. [402：統合レビューの接続](402-connect-post-handoff-review-to-exact-assembly.md)で、証拠付きレビューを最終的な統合結果と反映に結び付ける。
2. [403：統合担当による完了処理](403-complete-published-session-members-through-integration.md)で、反映と作業場所の削除を確認して正式に完了できるようにする。
3. [385：実セッションの証拠検証](385-verify-live-session-distinctness-from-bound-transcripts.md)を実装する。
   未着手のまま棚上げしていたプランを戻したもので、受け入れ条件と変更範囲は維持している。
4. 3件の完了後、隔離した生成プロジェクトで、別々の実セッションによる同時実装と直列の統合を実証する。
   実証だけの番号付きプランは作らず、製品コードを変更する独立した2件を使う。

実装と引き渡しの372、373、およびレビュー結果の証拠検証の384は完了済みである。
停止した379の再開やレビュー枠の初期化は行わない。
402と403は設計承認待ちであり、共有制御を変更するこれら3件の実装は直列に進める。
各プランの完了と、実際の並列開発を実証したことは分けて記録する。

## 外部の構造化判断とリスク予測

TypeSafeの登録を扱う345は、再構成した[400](../checked/2026/09/16-31/400-register-typesafe-with-canonical-host-detection.md)として完了した。
354は[重み付き特徴量による実装リスクの予測](../checked/2026/09/16-31/354-score-plan-risk-from-weighted-features.md)として完了した。

## 図、操作動画、スキル

元の368は独立した4つの機能を抱き合わせていたため、4件に分けた。
4件は登録用のファイルを共有するため、一件ずつ実装する。

- [368：根拠付きの図の生成と完了前の鮮度検査](368-generate-evidence-bound-project-diagrams.md)
- [391：Web画面の操作の録画とRemotionによる字幕付き動画](391-record-web-ui-demos-with-remotion.md)
  368の設定、コマンド、完了前の検査を拡張するため、368の完了後に開始する。
  Remotionはオーナーの判断で維持する。従業員4名以上の営利組織には有料ライセンスが必要になる。
- [390：Exa検索に限ったAgent Reachの調査手順](390-add-agent-reach-exa-search-guidance.md)
  外部サービスとして登録し、依存のインストールとCookieの取り込みは行わない。
- [393：grilling-vizによる意見の収集](393-vendor-grilling-viz-opinion-questionnaires.md)

## 昇格するときの確認

実装を開始する際は、進行中プランの枠が空いていることと、各プランの前提作業が完了していることを確認する。
前提作業への参照は、`docs/plan/checked.md`から実在する完了記録に解決してから昇格する。
context_files と integration_gates が実在するプランを指すことは、377が検査に組み込んだ。

いずれのプランも、既存の必須検証を保つことと、生成済みプロジェクトの更新で製品コードやプロジェクト所有の設定を保持することを完了条件に含める。

## 完了した系列

以前ここに記載していた作業は、現在の未着手一覧から外した。

- 開発手続きの改善として追加した310から313は完了した。[調査結果と根拠](../development-improvements-20260912.md)に、再利用した範囲と完了条件をまとめている。
- ハーネスのモデル更新への対応は、319の比較ツールと、320から再構成した328の補助指示の版選択で完了した。
- モデル情報の記録と確認は、318の取得と保存、321の表示と集計で完了した。
- 実装前の設計確認を具体化する342は完了した。
- 別セッションでの同時実装は、372と373が完了した。374は4件に再構成し、オーナーの指示で後継の379から382を棚上げした。
- プラン参照の解決は377と376で、レビュー証拠の経路は333、335、344で完了した。

個別の完了、再構成、棚上げの履歴は[checkedの一覧](../checked.md)、[replannedの一覧](../replanned.md)、[棚上げしたプランのディレクトリ](../shelved/)で確認できる。
