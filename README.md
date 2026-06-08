# Project Agent Workflow

プロジェクト管理、エージェント向けファイルルーティング、リポジトリ内のファイル管理を再利用できるようにする Codex ワークフローパッケージです。

このリポジトリは、役割ごとに小さく分けています。

- `SKILL.md`: Codex がこのワークフローをいつ、どのように使うかを定義します。
- `references/`: 必要なときだけ読む詳細な運用ガイドを置きます。
- `copier.yml`: 長期運用するための Copier テンプレート設定です。
- `template/`: 生成先リポジトリへ展開されるファイル群です。
- `scripts/init-project-workflow.sh`: 簡単に導入するための Copier ラッパーです。
- `scripts/lint-project-workflow.sh`: このパッケージが導入可能な状態かを検証します。

## リポジトリへ導入する

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

## 検証

```sh
scripts/lint-project-workflow.sh
tests/smoke.sh
```
