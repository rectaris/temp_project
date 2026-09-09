# 変更履歴

## 未リリース

## 2026-09-09 v1.4.5

- 受入条件と最も早い検証witnessの対応付けを、root と生成 project の双方で同じ規定として固定しました。
  witness map の方針文を AGENTS と orchestration の各文書で一意に特定し、段階名、静的witnessの述語、`authoritative_only_reason`、最終検証suiteを弱めない条件を marker として検査したうえで、root と生成側の一致を求めます。
  witness enforcement を運ぶ生成 source を Copier 更新の単一 inventory へ結び付け、生成 project が map なしの統合lane と、限定検証で証明できるのに最終検証だけを最初のwitnessとする定義を拒否することを smoke で確認します。

- チーム共有用の HTML 報告を、project 所有の Git 追跡先 `docs/human-report/<report-id>/` へ明示コマンドで公開できるようにしました。
  公開は `human_report_shared_mode` で選択し、構造化 source を review 対象、HTML をそこから決定的に導出する公開物として扱います。
  公開コマンドは stage も commit もせず、上書きは明示 supersede だけを受け付けます。
  `verify-shared` は記録した source hash、決定的再生成、公開ゲート、merge conflict 標識を照合して、陳腐化や改変を fail-closed で停止します。

- 旧形式 witness の移行境界を、1 回だけ使える migration 所有の provenance 記録へ結合しました。
  clean commit から作った snapshot と Git-local の試行状態を、生存する元 guardian の capability 証明、repository 識別、source commit、socket 経路で束ね、更新後段は 同じ snapshot の再現と新しい challenge-response の成立を求めます。
  失効、複製、再送、guardian 交代、confine されていない socket は fail-closed で拒否し、snapshot と試行状態は単独では製品の受入証拠にも検証 witness にもなりません。
- plan境界で本文を含まないsession checkpointを発行し、異なる観測済みroot sessionから一度だけ後続planを開始するstaged経路を追加しました。
  agent log manifestにはprovider観測tokenと決定的proxy countを分離して保存し、独立reviewは継承turn 0の限定packetと1回の再review上限へ結合します。
- 権威検証の失敗後は、失敗した操作と終了statusを実行台帳へ固定し、読み取り専用の再現証拠が一つの影響対象invariantを確認するまで修復planの作成を拒否するようにしました。
- 進行中の統合planでは全受入条件を最初の静的検査、限定検証、または最終検証へdigestで対応付け、限定検証を飛ばす定義と理由のない最終検証専用定義を実行前に拒否するようにしました。
- Copier更新fixtureのsource copyとGit stagingを単一inventoryから生成し、重複、欠落、および再度の二重管理を検出する回帰検証を追加しました。
- 登録済みの linked worktree を local Git の ancestry、upstream、clean 状態、保護設定で scan し、固定 manifest を effect 直前に再検証して、明示確認がある場合だけ通常の worktree・branch 削除を行う local retirement workflow を追加しました。生成 project は safe-disabled で開始し、Copier 更新では project-owned 設定を保持します。
- 外部 provider の認証確認を、実際の provider、コマンド実行境界、credential source へ結合し、sandbox 内外や provider 切替時の認証事実を別の呼び出しへ流用しないようにしました。
- 書き込み可能な逐次workerを、commit済みplanから毎回生成する読み取り専用の実行契約へ結合し、曖昧なdirectory範囲、保護対象、検証権限への書き込みを起動前に拒否するようにしました。
- 事前に固定した通常scenarioと独立holdoutを同じworker契約評価器で実行し、観測結果をfixture、runner、元planの受入条件digestへ結合する統合証拠を追加しました。
- worker完了受領書を契約、試行、process結果、候補差分へ結合し、通常case、既知の回帰case、独立holdoutの観測結果を元planの受入条件digestへ結び付ける統合証拠を追加しました。
- 対象とテンプレートの元リポジトリを変更せず、固定したGit commit間のCopier更新、安全性、製品検証、冪等性を一時cloneで証明してローカルmanifestへ記録するスキルを追加しました。
- 独立して修復できる局所障害では元planを置換せず、該当する実行だけを停止して修復planの完了後に新しい実行として再開するようにしました。
- 依存する書き込みplanの開始を、前planの親受理済み候補、適用commit、終了event、および一度だけ消費できる後続claimへ結合し、一つの依存chainで試行が重ならないようにしました。
  plan・sourceの基準と試行IDを契約、受領書、manifest、lifecycleで再照合し、却下と修正依頼は具体的な指摘を台帳外に保ったまま親の固定理由codeとreview証拠digestだけを追記します。

## 2026-08-15 v1.4.4

- `npm ci` が生成する Workerd の hardlink を単一 link の私有依存スナップショットへ正規化し、コピー中の source tree 変更を拒否するようにしました。
- Copier 更新後の未追跡ファイルも所有境界検査へ含め、更新済み ownership inventory を固定 digest と安全な file descriptor 読み取りで検証するようにしました。
- 隔離 npm 検証で project の Node major、私有 npm runtime、Playwright browser artifact、コマンド単位の Vite cache overlay を検証するようにしました。
- 再計画された後継を active・checked・replanned の排他的な索引状態から解決し、archive identity、status、継承受入れ条件の不一致を拒否するようにしました。

## 2026-08-15 v1.4.3

- 公開済みの release tag を含む checkout でも、Copier update fixture の同名 tag を一時 clone 内だけで更新して実更新の検証を継続できるようにしました。

## 2026-08-15 v1.4.2

- Hook と検証ツールの大規模なテストモジュールを責務別 package へ分割し、Copier inventory を専用 module へ整理しました。
- agent 向けの配置規約を `scripts/AGENTS.md` と `tests/AGENTS.md` に追加しました。
- v1.2.1 の未変更な逐次 plan worker だけを読み取り専用契約へ移行し、Copier 更新前の clean HEAD を基準にプロジェクト所有ファイルの未許可変更を拒否するようにしました。
- `package-lock.json` と完全な tree digest に結び付いた npm 依存スナップショットを作成し、隔離検証では親の私有コピーだけを新規 clone へ読み取り専用で提供するようにしました。
- v1.4.1 の実行中ラッパーが更新後のファイルを途中から読み直す問題を修正し、現行 helper 自身の置換後も最終検証まで完了する回帰テストを追加しました。

## 2026-08-13 v1.4.1

- plan worker の後続操作を manifest の plan と execution ledger へ結合し、旧 archive の focused validation 互換性、dirty path scope、symlink 適用後の復旧処理を修正しました。
- writable worker の model 選択説明を risk と ambiguity に基づく実装へ合わせ、再構成された plan の履歴・契約・検証コマンドを planning guide に追記しました。

## 2026-08-13 v1.4.0

- plan の実行境界が不適切と判明した場合に `replan_required` で停止し、元の要件と受入れ条件を保持したまま後続 plan へ再構成する lifecycle 契約を追加しました。
- 停止した plan の HEAD、本文、受入れ条件、dirty path、後続割当てを検証し、再構成履歴・契約・後続 plan・索引を排他遷移する `restructure-plan.py` を追加しました。
- 委譲と親直接実装の実行・レビュー予算を外部 ledger へ記録し、強制再構成条件の後は sandboxed runner の全操作を開始前に拒否するようにしました。
- plan 再構成の停止条件と要件保持を固定 scenario と未調整 holdout で検証し、Copier 更新でもプロジェクト所有の再計画履歴を保持するようにしました。
- CI autofix workflow を patch artifact のみを生成する fail-closed 動作へ変更し、保存済みの `direct_push` Copier 回答も外部書き込みなしで互換維持するようにしました。
- sandboxed plan worker の候補 patch の path 導出で Git object database を一時領域へ隔離し、source object database へ候補 blob を書き込まないようにしました。
- orchestration 生成物の更新前チェックを Copier 更新ハーネスの simulation source と stage の対象へ追加し、更新時の現行 semantics 検証を固定しました。
- 委譲を repository 規模ではなく独立した価値と実装 slice で判断し、逐次 worker を実装 risk・曖昧さに応じて Spark または Terra へ振り分け、high と書き込み用 Sol を拒否するようにしました。
- 逐次 worker に run 単位の bounded availability state と親生成 telemetry を追加し、同一 run で利用不能と判定済みの model を再起動しないようにしました。
- 親 review で却下した候補を source へ適用せず、新規隔離 clone 内で最大2回まで局所修正し、original HEAD に対する aggregate patch を再生成できるようにしました。
- 候補生成から全 plan 検証を外し、親の diff・critical invariant review 後に focused 検証、受入れ直前に authoritative 検証を各隔離 clone で実行する段階的受入れへ変更しました。

## 2026-08-13 v1.3.0

- 逐次 plan worker は GPT-5.3-Codex-Spark / medium を優先し、Codex CLI が利用不能を報告した場合だけ、新しい隔離環境で GPT-5.6-Luna / max を一度使用するようにしました。
- README の Copier 導入手順を現在の `v1.2.1` に合わせ、バージョンを指定しない最新安定版、固定 tag、開発版の最新コミットの選択方法を区別しました。
- ルートリポジトリに GitHub の正確な操作、対象、効果を直前に検査し、保護された効果を確認または拒否する task-scoped 外部サービス方針と検査入口を追加しました。

## v1.2.1

- 新規 tag の push で `before` が全ゼロになる場合は、CI の whitespace gate が tag commit と直前 commit の差分だけを検査するようにしました。
- Copier 更新テストの target tag を専用 commit に分離し、同じ commit に実際の release tag が存在しても回答ファイルの期待値が変わらないようにしました。

## v1.2.0

- タスクに応じた固定モデルと reasoning effort を Codex helper agent に設定しました。
- 小規模で境界が確定した実装を担当する GPT-5.3-Codex-Spark の helper agent を追加しました。
- 複数の証拠を読み取り専用で比較する GPT-5.6-Luna / xhigh の helper agent を追加しました。
- Copier の copy/update 後に `.codex/agents/*.toml` の `model` と `model_reasoning_effort` だけを固定値へ正規化する task を追加しました。
- post-render task の実行に必要な `--trust` と、agent 設定ファイルのフィールド単位の所有境界を利用者向け文書へ反映しました。
- 開発者向けの進捗報告や判断資料を構造化入力から評価し、必要な場合だけ Git 対象外の単一 HTML としてローカル生成する機能を追加しました。
- HTML の生成判断を無効化できる `human_report_mode` と、機密情報、入力元、出力先を検査する生成先 CLI を追加しました。

## v1.1.2

- `.project-agent-workflow/docs/agent/` の規範文書を context compression の対象外にしました。
- v0 系からの adoption で、移行元の生成内容と一致する旧ルート CLI だけを managed core への互換 bridge に置換するようにしました。
- 変更済みまたは検証不能な旧ルート CLI を通常位置に保持し、migration manifest と標準出力で手動確認を求めるようにしました。
- 移行前の active plan と checked plan を書き換えず、移行後も検証できる互換処理を追加しました。
- 生成先が削除した `docs/plan/` の `.gitkeep` を通常の update で再生成しないようにしました。
- v1.1.2 の adoption と通常 update を、異なる履歴と製品検証を持つ複数の生成先リポジトリで隔離検証しました。
