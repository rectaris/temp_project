# Codex CI Autofix

**Codex CI Autofix** は、PR の通常 CI が失敗したときに Codex GitHub Action で最小修正を試す GitHub Actions ワークフローです。

この仕組みは同一リポジトリ内の PR ブランチだけを対象にします。

fork PR では write token と `OPENAI_API_KEY` を使いません。

## Why This Exists

`@codex fix the CI failures` は単発の Codex タスクとして動くため、CI が再実行されてまだ失敗した場合に自動で次の修正試行へ進みません。

このリポジトリの `codex-ci-autofix.yml` は、`CI` workflow の失敗を `workflow_run` で受け取り、上限回数まで修正コミットを試します。

CI が通ればループは止まります。

上限回数に達した場合も止まります。

## Workflow Interaction

`.github/workflows/project-agent-workflow.yml` は通常の検証 workflow です。

`pull_request`、`push`、`workflow_dispatch` で実行されます。

`.github/workflows/codex-ci-autofix.yml` は `CI` workflow の完了を監視します。

`CI` が PR イベントで失敗し、PR ブランチが同一リポジトリにある場合だけ Codex を起動します。

Codex は `.github/codex/prompts/ci-autofix.md` の指示を受け取り、`gh run view "$FAILED_RUN_ID" --log-failed` で失敗ログを確認します。

Codex はファイルを編集できますが、commit、push、merge はしません。

workflow の後段 job が差分を patch artifact にします。

`patch-only` mode では、workflow は patch artifact だけを残します。

`direct-push` mode では、後段 job が `fix: codex ci autofix` として PR ブランチへ push します。

Copier の既定値は `disabled` です。

`patch_only` または `direct_push` を生成時に明示的に選択した場合だけ、`.github/workflows/codex-ci-autofix.yml` を生成します。

`patch_only` は、workflow を有効にする場合の安全側の選択肢です。

## Required Secrets

`OPENAI_API_KEY` を GitHub repository secret に登録してください。

Codex GitHub Action はこの secret を使って Codex CLI を実行します。

`GITHUB_TOKEN` は GitHub Actions が発行する標準 token を使います。

workflow の write 権限は patch を適用して PR ブランチへ commit する job に限定しています。

## Enable Or Disable

有効化するには `ci_autofix_mode` を `patch_only` または `direct_push` に変更し、Copier update で `.github/workflows/codex-ci-autofix.yml` を生成します。

無効化するには `ci_autofix_mode` を `disabled` に変更して Copier update を実行します。

手動実行ごとに動作を変える場合は、`workflow_dispatch` の `mode` を選択してください。

自動実行の既定値を変更する場合は、Copier の `ci_autofix_mode` 回答を更新します。

## Fork PR Restriction

fork PR では、外部 contributor が変更したコードが workflow 上で実行される可能性があります。

その状況で write token や `OPENAI_API_KEY` を渡すと、secret の露出や不正な repository 書き込みにつながります。

このため、workflow は `head_repository.full_name` または PR の `head.repo.full_name` が現在の repository と一致しない場合に停止します。

## Attempt Guard

既定の上限は 3 回です。

workflow は base branch から PR HEAD までの commit subject を見て、`fix: codex ci autofix` の数を数えます。

数が `max_attempts` 以上の場合、Codex を起動せずに終了します。

manual dispatch では `max_attempts` を変更できます。

## Manual Test

GitHub Actions の `Codex CI Autofix` から `Run workflow` を選びます。

`pr_number` に同一リポジトリ PR の番号を指定します。

`failed_run_id` を省略した場合、workflow はその PR HEAD に紐づく最新の失敗した `CI` run を探します。

`mode` に `patch-only` を指定すると、push せず artifact だけを生成します。

## Review Generated Commits

生成された commit は `fix: codex ci autofix` という subject になります。

PR の Files changed と commit diff を確認してください。

テストを弱める変更、失敗テストの削除、secret や deployment 設定の変更が入っている場合は採用しないでください。

必要ならその commit を revert してください。

## Revert

仕組み全体を戻すには、`.github/workflows/codex-ci-autofix.yml`、`.github/codex/prompts/ci-autofix.md`、この文書、`AGENTS.md` の CI autofix section を削除します。

通常 CI から `workflow_dispatch` を外したい場合は、`.github/workflows/project-agent-workflow.yml` の該当 trigger も戻します。
