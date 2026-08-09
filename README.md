# Project Agent Workflow

プロジェクト管理、エージェント向けファイルルーティング、リポジトリ内のファイル管理を再利用できるようにする Codex ワークフローパッケージです。

このリポジトリは、役割ごとに小さく分けています。

- `SKILL.md`: Codex がこのワークフローをいつ、どのように使うかを定義します。
- `references/`: 必要なときだけ読む詳細な運用ガイドを置きます。
- `copier.yml`: 長期運用するための Copier テンプレート設定です。
- `template/`: 生成先リポジトリへ展開されるファイル群です。
- `scripts/init-project-workflow.sh`: 簡単に導入するための Copier ラッパーです。
- `scripts/lint-project-workflow.sh`: このパッケージが導入可能な状態かを検証します。

生成先には、計画 lifecycle、変更差分に応じた検証選択、静的セキュリティ検査、任意の NVIDIA SkillSpector スキャン手順、構造スキャン、handoff 管理、active plan の文脈抽出、ローカル agent ログ方針、任意の context 圧縮 helper、Codex hook/config 検証の汎用ルールを導入できます。
MCP、Linear、graph memory のような外部サービス依存ルールは Copier の回答で opt-in します。

リリースごとの変更内容は [CHANGELOG.md](CHANGELOG.md) に記録します。

Copier が更新する汎用ファイルは、生成先の `.project-agent-workflow/` にまとめます。
ルートの `AGENTS.md`、`README.md`、`docs/agent/`、`docs/plan/` など、開発中に変更するファイルは初回だけ生成し、以後の `copier update` では上書きしません。
`.agents/skills/` には管理対象の汎用 Skill 用ブリッジを置き、予約名と衝突しないプロジェクト固有 Skill も追加できます。
`.codex/` と `.github/` には、ホストが検出するための小さな橋渡しファイルまたは専用の統合ファイルだけを置きます。
`.codex/agents/*.toml` はプロジェクト所有ですが、`model` と `model_reasoning_effort` だけはテンプレートが固定し、copy/update 後の task で正規化します。
agent の説明、指示、sandbox 設定など、ほかのフィールドは変更しません。

このテンプレートは、対応する Copier の copy/update 経路で、生成先が所有する製品コード、規則、設定、計画履歴、検証処理を削除または上書きしないことを開発要件とします。
更新テストでは、競合、`*.rej`、分類できない Git 管理対象ファイルの削除がなく、生成先固有の検証が引き続き実行できることを確認します。
Copier 管理ファイルと、固定対象である agent model の2項目は更新されるため、すべてのファイルが不変になるという意味ではありません。

ローカル agent ログは生成先の `.agent-logs/` と `.agent-artifacts/` に保存する方針を常に生成します。
これらは Git 管理外の情報資産として扱い、`docs/plan` には raw log ではなく要約、判断、検証結果、必要な run id を残します。
大きなログを読み返す場合は `.project-agent-workflow/docs/agent/spec-index.yaml` のルーティング、manifest、検索、抜粋、`.project-agent-workflow/scripts/context-compress.sh` を使います。
Headroom は PATH 上にある場合だけ任意 backend として使い、テンプレートの必須依存にはしません。

外部サービスを opt-in した生成先には、`.project-agent-workflow/docs/agent/SPEC_EXTERNAL_SERVICES.md` が生成されます。
このドキュメントには、認証情報の置き場所、dry-run/read/write の分類、MCP server の記録項目、Linear の issue sync 境界、graph memory の project id と write review 境界を記載します。
外部連携を無効にした場合も、同じファイルに「ローカル運用で十分であること」と後から有効化する際の追加項目を残します。

## リポジトリへ導入する

以下の直接導入は、新規リポジトリまたは同名ファイルを置き換えてよいリポジトリを対象にします。

既存のエージェント規範や計画履歴を持つリポジトリでは、一時ディレクトリへ生成し、対象リポジトリとの差分を確認してからファイル単位で取り込んでください。
同名ファイルは直接上書きせず、プロジェクト固有の規則を保持して手動で統合します。

GitHub から直接導入する場合:

```sh
copier copy --trust https://github.com/rectaris/temp_project.git /path/to/repo
```

安定版タグを指定する場合:

```sh
copier copy --trust --vcs-ref v0.3.0 https://github.com/rectaris/temp_project.git /path/to/repo
```

推奨:

```sh
copier copy --trust /path/to/project-agent-workflow /path/to/repo
```

ラッパー:

```sh
scripts/init-project-workflow.sh /path/to/repo
```

対話なしでデフォルト回答を使って生成する場合:

```sh
copier copy -f --trust /path/to/project-agent-workflow /path/to/repo
```

生成された `.copier-answers.yml` はコミットしてください。これにより、あとから `copier update` でテンプレート更新を追従できます。

このテンプレートは copy/update 後に agent model の固定項目を正規化する task を実行するため、すべての Copier コマンドで `--trust` が必要です。
`--trust` は同梱 task の実行を許可するだけであり、差分の安全性を保証しないため、既存リポジトリでは clean な状態から実行して差分と検証結果を確認してください。

## 生成済みリポジトリを更新する

生成先リポジトリで次を実行します。

```sh
copier update --trust
```

v0 系のルート配置からは、`copier update --vcs-ref v1.0.0` と `copier update --vcs-ref v1.1.0` を実行しないでください。

公開済みの v1.0.0 は、カスタマイズ済みの旧ファイルを Copier の smart diff で新しい bridge へ再適用し、未解決競合や追跡ファイル削除を残す場合があります。

公開済みの v1.1.0 は、Git 管理対象外の依存環境を競合として誤検出し、migration backup を現行コードとして検証する場合があります。

公開済みの v1.1.1 は、`.project-agent-workflow/docs/agent/` の規範文書を context compression の拒否対象に含めていません。

v1.1.2 以降へ初めて移行する場合は、clean な生成先リポジトリで、checkout 済みテンプレートの専用スクリプトを実行します。

```sh
uv run --with copier python ../temp_project/scripts/adopt-to-namespaced-layout.py \
  --destination . \
  --vcs-ref v1.1.2
```

この処理は旧ファイルを `.project-agent-workflow-migration/v1-pre-namespace/` へコピーしてから `copier recopy` を使い、新しい管理領域を追加します。
既存のプロジェクト規則、利用者が変更したスクリプト、Skill、計画、製品用 workflow は元のパスに残します。
旧 Hook 実装だけはバックアップ後に安定した bridge へ置換します。
旧ルート CLI は、移行元 tag の `template/scripts/` にある生成内容と通常位置のファイルが byte 単位で一致する場合だけ、managed core を実行する互換 bridge へ置換します。
変更済みファイル、symbolic link、移行元 tag の Git object を取得できないファイルは通常位置に保持し、manifest と標準出力で手動確認を求めます。
ほかの旧スクリプトから import される Python module は互換 bridge の対象にしません。
v1.0.0 の tag には旧 `template/scripts/` がないため、v1.0.0 修復時の旧ルート CLI は自動置換せず保持します。
更新後は manifest と、旧 Copier tag を参照しているプロジェクト所有ファイルを確認してください。
`.copier-answers.yml` が v1 系を記録した後は、通常の `copier update --trust` を使います。

すでに v1.1.0 または v1.1.1 の導入結果を commit している場合は、`copier update --trust --vcs-ref v1.1.2` で managed core、Stop Hook の配線、context compression の拒否境界を修正します。

Copier の競合は、対象ファイル内の `<<<<<<<`、`=======`、`>>>>>>>` または `*.rej` ファイルとして現れる場合があります。
導入スクリプトは、旧テンプレートファイルを先にバックアップします。
旧テンプレートの生成内容と一致する任意機能のファイルだけは、新設定に応じて通常位置から廃止するか managed core への互換 bridge に置き換え、manifest に記録します。
利用者が変更したファイルと分類できないファイルは削除せず、通常位置と退避先の両方に残すため、migration manifest と差分を確認してください。
コミット前に両方を検索し、差分へ必要な内容を統合してから競合表示を解消してください。
`*.rej` は内容を採用または却下した後に削除します。

安定版テンプレートには Git tag を付けると、生成先リポジトリが更新対象のバージョンを安定して解決できます。

タグ付きバージョンへ明示的に更新する場合:

```sh
copier update --trust --vcs-ref v0.3.0
```

リリース時は、テンプレート変更をコミットしたあとにタグを作成して push します。

タグの `X.Y.Z` は、直近の安定版タグからの変更内容で決めます。

- `X`: 既存の生成先リポジトリで手動移行が必要になる破壊的変更を入れたときに上げます。
- `Y`: `copier.yml` の質問追加、`template/` の機能追加、生成される運用ルールの追加など、後方互換の機能追加を入れたときに上げます。
- `Z`: 誤記修正、検証の補強、後方互換のバグ修正など、既存機能の修正に限るときに上げます。

判断に迷う場合は、`git diff <latest-tag>..HEAD -- copier.yml template scripts tests docs references README.md` で生成契約と運用手順への影響を確認します。

```sh
git tag vX.Y.Z
git push origin main --tags
```

## 検証

初回は `uv` で依存関係を同期します。

```sh
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run copier --version
```

```sh
scripts/lint-project-workflow.sh
tests/smoke.sh
tests/test-hooks.py
tests/copier-update.sh
```

CI は固定版の PyYAML で生成 YAML を解析し、checksum を確認した actionlint 1.7.12 で GitHub Actions workflow を検査します。
CI では `uv sync` したうえで、生成テストと更新テストを必須として実行します。
PATH 上に `copier` が無い場合、`tests/smoke.sh` と `tests/copier-update.sh` は `uv run copier` を使います。
`uv` も無い場合は生成系の検証をスキップします。
