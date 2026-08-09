# 変更履歴

## 未リリース

- タスクに応じた固定モデルと reasoning effort を Codex helper agent に設定しました。
- 小規模で境界が確定した実装を担当する GPT-5.3-Codex-Spark の helper agent を追加しました。
- 複数の証拠を読み取り専用で比較する GPT-5.6-Luna / xhigh の helper agent を追加しました。
- Copier の copy/update 後に `.codex/agents/*.toml` の `model` と `model_reasoning_effort` だけを固定値へ正規化する task を追加しました。
- post-render task の実行に必要な `--trust` と、agent 設定ファイルのフィールド単位の所有境界を利用者向け文書へ反映しました。

## v1.1.2

- `.project-agent-workflow/docs/agent/` の規範文書を context compression の対象外にしました。
- v0 系からの adoption で、移行元の生成内容と一致する旧ルート CLI だけを managed core への互換 bridge に置換するようにしました。
- 変更済みまたは検証不能な旧ルート CLI を通常位置に保持し、migration manifest と標準出力で手動確認を求めるようにしました。
- 移行前の active plan と checked plan を書き換えず、移行後も検証できる互換処理を追加しました。
- 生成先が削除した `docs/plan/` の `.gitkeep` を通常の update で再生成しないようにしました。
- v1.1.2 の adoption と通常 update を、異なる履歴と製品検証を持つ複数の生成先リポジトリで隔離検証しました。
