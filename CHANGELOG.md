# 変更履歴

## 未リリース

- README の Copier 導入手順を現在の `v1.2.1` に合わせ、バージョンを指定しない最新安定版、固定 tag、開発版の最新コミットの選択方法を区別しました。

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
