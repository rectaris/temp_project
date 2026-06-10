# Project Agent Workflow

プロジェクト管理、エージェント向けファイルルーティング、リポジトリ内のファイル管理を再利用できるようにする Codex ワークフローパッケージです。

このリポジトリは、役割ごとに小さく分けています。

- `SKILL.md`: Codex がこのワークフローをいつ、どのように使うかを定義します。
- `references/`: 必要なときだけ読む詳細な運用ガイドを置きます。
- `copier.yml`: 長期運用するための Copier テンプレート設定です。
- `template/`: 生成先リポジトリへ展開されるファイル群です。
- `scripts/init-project-workflow.sh`: 簡単に導入するための Copier ラッパーです。
- `scripts/lint-project-workflow.sh`: このパッケージが導入可能な状態かを検証します。

生成先には、計画 lifecycle、変更差分に応じた検証選択、静的セキュリティ検査、構造スキャン、handoff 管理、active plan の文脈抽出、Codex hook/config 検証の汎用ルールを導入できます。MCP、Linear、graph memory のような外部サービス依存ルールは Copier の回答で opt-in します。

外部サービスを opt-in した生成先には、`docs/agent/SPEC_EXTERNAL_SERVICES.md` が生成されます。このドキュメントには、認証情報の置き場所、dry-run/read/write の分類、MCP server の記録項目、Linear の issue sync 境界、graph memory の project id と write review 境界を記載します。外部連携を無効にした場合も、同じファイルに「ローカル運用で十分であること」と後から有効化する際の追加項目を残します。

## リポジトリへ導入する

GitHub から直接導入する場合:

```sh
copier copy https://github.com/rectaris/temp_project.git /path/to/repo
```

安定版タグを指定する場合:

```sh
copier copy --vcs-ref v0.2.0 https://github.com/rectaris/temp_project.git /path/to/repo
```

推奨:

```sh
copier copy /path/to/project-agent-workflow /path/to/repo
```

ラッパー:

```sh
scripts/init-project-workflow.sh /path/to/repo
```

対話なしでデフォルト回答を使って生成する場合:

```sh
copier copy -f /path/to/project-agent-workflow /path/to/repo
```

生成された `.copier-answers.yml` はコミットしてください。これにより、あとから `copier update` でテンプレート更新を追従できます。

## 生成済みリポジトリを更新する

生成先リポジトリで次を実行します。

```sh
copier update
```

`*.rej` ファイルが生成された場合は、コミット前に必ず手動で確認してください。安定版テンプレートには Git tag を付けると、生成先リポジトリが更新対象のバージョンを安定して解決できます。

タグ付きバージョンへ明示的に更新する場合:

```sh
copier update --vcs-ref v0.2.0
```

リリース時は、テンプレート変更をコミットしたあとにタグを作成して push します。

```sh
git tag vX.Y.Z
git push origin main --tags
```

## 検証

```sh
scripts/lint-project-workflow.sh
tests/smoke.sh
tests/test-hooks.py
tests/copier-update.sh
```

CI では Copier をインストールしたうえで、生成テストと更新テストを必須として実行します。ローカルで Copier が無い場合、`tests/smoke.sh` と `tests/copier-update.sh` は生成系の検証をスキップします。
