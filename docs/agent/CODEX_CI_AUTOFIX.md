# Codex CI Autofix

**Codex CI Autofix** は、PR の通常 CI が失敗したときに Codex GitHub Action で最小修正を試す GitHub Actions ワークフローです。

この仕組みは同一リポジトリ内の PR ブランチだけを対象にします。

fork PR では write token と `OPENAI_API_KEY` を使いません。

## Why This Exists

`@codex fix the CI failures` は単発の Codex タスクとして動くため、CI が再実行されてまだ失敗した場合に自動で次の修正を試しません。

このリポジトリの `codex-ci-autofix.yml` は、`CI` workflow の失敗を `workflow_run` で受け取り、確認用の patch artifact だけを生成します。

生成した artifact は workflow 自身では repository や pull request を変更しません。

## Workflow Interaction

`.github/workflows/ci.yml` は通常の検証 workflow です。

`pull_request`、`push`、`workflow_dispatch` で実行されます。

`.github/workflows/codex-ci-autofix.yml` は `CI` workflow の完了を監視します。

`CI` が PR イベントで失敗し、PR ブランチが同一リポジトリにある場合だけ Codex を起動します。

Codex は `.github/codex/prompts/ci-autofix.md` の指示を受け取り、`gh run view "$FAILED_RUN_ID" --log-failed` で失敗ログを確認します。

Codex はファイルを編集できますが、commit、push、merge はしません。

`generate-fix` job は差分を patch artifact にします。

PR が `.github/codex/prompts/ci-autofix.md` を変更している場合、`generate-fix` job は Codex の実行前に停止します。

Codex に渡す prompt は、PR の作業ツリーではなく、取得済み base branch から読み出します。

workflow は dependency installer の前後で checkout の状態を確認し、tracked、staged、または無視されていない untracked path が変わった場合は Codex の実行前に停止します。

workflow に branch、issue、pull request の write permission を持つ job はありません。

すべての実行は patch-only の artifact 出力です。

## Required Secrets

`OPENAI_API_KEY` を GitHub repository secret に登録してください。

Codex GitHub Action はこの secret を使って Codex CLI を実行します。

`GITHUB_TOKEN` は GitHub Actions が発行する標準 token を使います。

workflow の job は repository の読み取りに必要な permission だけを持ち、branch、issue、pull request への write permission を持ちません。

## Enable Or Disable

有効化するには `.github/workflows/codex-ci-autofix.yml` を repository の default branch に置きます。

無効化するには GitHub Actions の workflow 一覧で `Codex CI Autofix` を disable にするか、この YAML ファイルを削除します。

`workflow_dispatch` では `pr_number` と任意の `failed_run_id` だけを指定し、実行モードは選択しません。

## Fork PR Restriction

fork PR では、外部 contributor が変更したコードが workflow 上で実行される可能性があります。

その状況で write token や `OPENAI_API_KEY` を渡すと、secret の露出や不正な repository 書き込みにつながります。

このため、workflow は `head_repository.full_name` または PR の `head.repo.full_name` が現在の repository と一致しない場合に停止します。

## Manual Run

GitHub Actions の `Codex CI Autofix` から `Run workflow` を選びます。

`pr_number` に同一リポジトリ PR の番号を指定します。

`failed_run_id` を省略した場合、workflow はその PR HEAD に紐づく最新の失敗した `CI` run を探します。

workflow は patch artifact を生成し、branch や pull request を変更しません。

## Review Patch Artifact

生成された patch artifact をダウンロードし、適用前に diff を確認してください。

テストを弱める変更、失敗テストの削除、secret や deployment 設定の変更が入っている場合は採用しないでください。

## Revert

仕組み全体を戻すには、`.github/workflows/codex-ci-autofix.yml`、`.github/codex/prompts/ci-autofix.md`、この文書、`AGENTS.md` の CI autofix section を削除します。

通常 CI から `workflow_dispatch` を外したい場合は、`.github/workflows/ci.yml` の該当 trigger も戻します。
