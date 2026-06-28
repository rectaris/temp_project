# Agent Logging and Context Compression

## Manifest

- `status`: `active`
- `task_type`: `planning_docs`
- `review_class`: `B`
- `human_design_required`: `no`
- `human_approval_status`: `not_required`
- `target_files`:
  - `copier.yml`
  - `README.md`
  - `template/AGENTS.md.jinja`
  - `template/docs/agent/spec-index.yaml.jinja`
  - `template/docs/agent/SPEC_AGENT_LOGGING.md`
  - `template/docs/agent/SPEC_CONTEXT_COMPRESSION.md`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/scripts/context-compress.sh`
  - `template/.gitignore`
  - `tests/`
- `required_specs`:
  - `AGENTS.md`
  - `template/docs/agent/SPEC_PLAN_WORKFLOW.md`
  - `template/docs/agent/SPEC_DEVELOPMENT_FLOW.md.jinja`
  - `docs/agent/SPEC_JAPANESE_TECH_WRITING.md`
- `validation`:
  - `scripts/lint-project-workflow.sh`
  - `tests/smoke.sh`
- `acceptance`:
  - Generated projects document local agent raw logs without making raw logs a Git-managed source of truth.
  - Generated projects always have a context-compression policy that lets agents decide when to use available tooling.
  - Headroom is supported as an optional command-line backend, not as a required template dependency.
  - Normative routing and validation documents remain read as source text and are not compressed by default.
- `acceptance_focus`:
  - local-only forensic logs
  - route-based compression decisions
  - optional Headroom wrapper
- `expected_output`: template files, policy docs, and tests for agent logging and context compression.
- `checked_summary_ja`: 生成先にローカル agent ログ方針と任意の Headroom 対応 context 圧縮ルートを追加した。
- `completion_deferred_reason`: ``

## Goal

生成先プロジェクトが agent 作業の証跡を必要に応じて保存し、巨大な raw log や artifact を扱うときだけ context 圧縮を検討できるようにする。

Headroom は標準依存にしない。

Headroom が利用可能な環境では、agent がテキストルーティングで対象を判断し、薄い wrapper を通じて raw log、CI log、巨大 stdout、JSON dump などを圧縮候補として扱えるようにする。

## Design

`docs/plan` には後続 agent が読む要約、判断、検証結果、commit 情報を残す。

Raw log は `.agent-logs/` に分離し、巨大 artifact は `.agent-artifacts/` に分離する。

これらのディレクトリは生成先で Git 管理しない。

Raw log は、ユーザー依頼、assistant の可視メッセージ、実行コマンド、stdout、stderr、差分、検証結果、参照パスなど、観測可能な作業証跡を保存する場所として定義する。

ただし、secrets、tokens、`.env`、不要な個人情報、保存不能な内部思考、大きすぎる binary は除外または artifact 参照にする。

要約ログは raw log の代替ではなく、raw log への索引として扱う。

Context compression policy は常に生成する。

Headroom の利用可否は `copier copy` 時点で固定しない。

Agent は `spec-index.yaml` の routing に従い、`.agent-logs/`、`.agent-artifacts/`、CI log、巨大 stdout、巨大 JSON、検索結果、API response、context overflow を扱うときだけ `SPEC_CONTEXT_COMPRESSION.md` を読む。

`AGENTS.md`、`docs/agent/SPEC_*.md`、検証ルール、セキュリティルールのような規範文書は圧縮せず、必要な原文を読む。

Headroom が PATH 上にある場合だけ、`template/scripts/context-compress.sh` が任意 backend として呼び出せる。

Headroom が無い場合は検索、分割読み、抜粋へ戻し、作業を止めない。

## Tasks

- [ ] 既存 template 生成物と lint/smoke の期待値を確認する。
- [ ] `.agent-logs/` と `.agent-artifacts/` を生成先で Git 管理しない方針を追加する。
- [ ] `SPEC_AGENT_LOGGING.md` を追加し、raw log、要約、manifest、redaction、保持期間、Git 管理境界を定義する。
- [ ] `SPEC_CONTEXT_COMPRESSION.md` を追加し、Headroom を含む optional backend の使用判断を定義する。
- [ ] `spec-index.yaml.jinja` に agent logging と context compression の conditional routing を追加する。
- [ ] `AGENTS.md.jinja` と開発フロー文書に、raw log はローカル証跡であり主記録ではないことを反映する。
- [ ] `context-compress.sh` を追加し、Headroom がある場合だけ圧縮を試す薄い wrapper にする。
- [ ] Copier 生成テストと smoke test を更新する。
- [ ] `scripts/lint-project-workflow.sh` と `tests/smoke.sh` を実行する。

## Open Decisions

- Raw log 機構を常に文書化し、実ディレクトリだけ `.gitignore` で受ける形にするか、Copier option で方針文書ごと切り替えるか。
- `context-compress.sh` の入力を単一ファイルに限定するか、ディレクトリ manifest を受ける形まで含めるか。
- Headroom の出力形式を template 側で固定するか、最小限の manifest 記録だけを求めるか。

## Validation Notes

この計画を実装するときは、生成先に余計な必須依存を追加していないことを確認する。

Headroom が未導入の環境でも、生成先の通常 workflow、plan lint、smoke test が通ることを確認する。
