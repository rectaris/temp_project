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
  - Generated projects treat raw logs as retained local information assets and control reading through routing, indexes, and manifests.
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

Raw log は原則保持する情報資産として扱い、自動削除期限は設けない。

削除は明示操作だけで行い、`docs/plan` から参照された run は `pinned` として扱う。

Raw log の肥大化は保持期間ではなく、`spec-index.yaml`、index、manifest、検索、抜粋、context compression によって読み込み量を制御する。

Raw log は、ユーザー依頼、assistant の可視メッセージ、実行コマンド、stdout、stderr、差分、検証結果、参照パスなど、観測可能な作業証跡を保存する場所として定義する。

ただし、secrets、tokens、`.env`、不要な個人情報、保存不能な内部思考、大きすぎる binary は除外または artifact 参照にする。

要約ログは raw log の代替ではなく、raw log への索引として扱う。

Context compression policy は常に生成する。

Headroom の利用可否は `copier copy` 時点で固定しない。

Agent は `spec-index.yaml` の routing に従い、`.agent-logs/`、`.agent-artifacts/`、CI log、巨大 stdout、巨大 JSON、検索結果、API response、context overflow を扱うときだけ `SPEC_CONTEXT_COMPRESSION.md` を読む。

`AGENTS.md`、`docs/agent/SPEC_*.md`、検証ルール、セキュリティルールのような規範文書は圧縮せず、必要な原文を読む。

Headroom が PATH 上にある場合だけ、`template/scripts/context-compress.sh` が任意 backend として呼び出せる。

Headroom が無い場合は検索、分割読み、抜粋へ戻し、作業を止めない。

## Design Decisions

1. Raw log 機構は常に生成する。

   A: `SPEC_AGENT_LOGGING.md` と `.gitignore` ルールを常に生成する。

   B: Copier option で有効化した場合だけ生成する。

   C: 文書だけ常に生成し、実ディレクトリや script は生成しない。

   推奨: A

   理由: 方針文書と Git 管理外ルールは軽く、全生成先にあっても副作用が小さいため。

2. Raw log の既定保存場所は固定する。

   A: `.agent-logs/` と `.agent-artifacts/` に固定する。

   B: `.copier-answers.yml` で変更可能にする。

   C: `SPEC_AGENT_LOGGING.md` に例だけを書く。

   推奨: A

   理由: 固定パスの方が routing、ignore、script、検証を単純にできるため。

3. Raw log の保存対象は観測可能な証跡を標準対象にする。

   A: user request、assistant visible messages、tool calls、commands、stdout、stderr、diff、validation を標準対象にする。

   B: commands、validation、diff だけに絞る。

   C: すべての取得可能な payload を保存対象にする。

   推奨: A

   理由: 監査と再現に必要な情報を広く残しつつ、無制限保存より制御しやすいため。

4. 保存しない情報は明示する。

   A: secrets、tokens、`.env`、不要な個人情報、保存不能な内部思考、大きすぎる binary を禁止または別扱いにする。

   B: agent 判断に任せる。

   C: raw log はローカルなので禁止対象を設けない。

   推奨: A

   理由: 一時的に agent が見た情報と、永続保存する情報は境界が違うため。

5. Redaction は最小限の機械チェックと記録を持たせる。

   A: 最小限の pattern scan と redaction report を必須にする。

   B: agent の目視判断だけにする。

   C: 高度な secret scanner を必須依存にする。

   推奨: A

   理由: 必須依存を増やさず、最低限の安全弁と監査記録を持てるため。

6. Retention は自動削除ではなく原則保持にする。

   A: 既定 30 日で削除する。

   B: 既定 30 日だが、plan から参照された run は保持する。

   C: 削除期限を設けず、raw log を原則保持する。

   D: 期限ではなく、明示 archive/delete lifecycle で管理する。

   推奨: C + D

   理由: Raw log は情報資産として蓄積する価値があり、読み込み量は retention ではなく routing、index、manifest、検索、圧縮で制御するため。

7. Git 管理への混入は機械的に防ぐ。

   A: `.gitignore` と security/static check の両方で防ぐ。

   B: `.gitignore` のみで防ぐ。

   C: 文書で注意するだけにする。

   推奨: A

   理由: raw log は機密混入リスクが高いため、文書だけでなく deterministic check で守る必要があるため。

8. Manifest schema は構造化する。

   A: `manifest.json` を標準にする。

   B: `manifest.md` を標準にする。

   C: 形式を固定しない。

   推奨: A

   理由: script と agent が扱いやすく、source path、redaction、retention、compressed output を構造化できるため。

9. Headroom の呼び出し契約は薄い wrapper にする。

   A: `scripts/context-compress.sh <input> <output-dir>` のような単一ファイル入力にする。

   B: ディレクトリを受け取り、manifest ごと圧縮する。

   C: Headroom の CLI を直接使わせ、wrapper は置かない。

   推奨: A

   理由: 最初は単一ファイルの方が安全で、CI log、stdout、JSON dump など主要用途を満たせるため。

10. 圧縮対象の拒否ルールは script レベルでも持つ。

    A: `AGENTS.md`、`docs/agent/`、validation/security specs は wrapper が拒否する。

    B: 文書で禁止するだけにする。

    C: すべて圧縮可能にする。

    推奨: A

    理由: 原文精度が必要な規範文書は機械的に守る方が安全なため。

11. 圧縮結果は raw log run 配下の派生物として保存する。

    A: `.agent-logs/<run-id>/compressed/` に保存する。

    B: `.agent-artifacts/compressed/` に保存する。

    C: 標準出力だけに出して保存しない。

    推奨: A

    理由: 圧縮元、圧縮結果、manifest を同じ run 配下に置くと追跡しやすいため。

12. 圧縮結果は正本ではなく派生ビューとして扱う。

    A: 圧縮結果は派生ビューとし、必要時は raw log に戻る。

    B: 圧縮結果を正本として扱う。

    C: Headroom 使用時だけ正本扱いする。

    推奨: A

    理由: 圧縮は情報変換なので、監査や再現では raw log を正本にするべきなため。

13. Agent が Headroom を使う判断基準は routing と目安で決める。

    A: 行数、byte 数、token 見積もりの目安を spec に書く。

    B: agent の裁量だけに任せる。

    C: すべての `.agent-logs/` 読み取りで Headroom を試す。

    推奨: A

    理由: 完全自動化しなくても、目安があると agent ごとの判断ぶれを抑えられるため。

14. Headroom 未導入時は通常運用へ fallback する。

    A: fallback して検索、分割読み、抜粋に戻る。

    B: エラーで停止する。

    C: 導入手順を表示して終了する。

    推奨: A

    理由: Headroom は必須依存ではないため、未導入で通常作業が止まる設計は避けるべきなため。

15. テスト対象はテンプレート契約に限定する。

    A: 生成物存在、`.gitignore`、routing、wrapper fallback、拒否パスを smoke test する。

    B: 文書生成だけ確認する。

    C: Headroom 実体をインストールして圧縮までテストする。

    推奨: A

    理由: Headroom を必須依存にせず、テンプレートとして守るべき契約だけを deterministic に検証できるため。

## Tasks

- [ ] 既存 template 生成物と lint/smoke の期待値を確認する。
- [ ] `.agent-logs/` と `.agent-artifacts/` を生成先で Git 管理しない方針を追加する。
- [ ] `SPEC_AGENT_LOGGING.md` を追加し、raw log、要約、manifest、redaction、原則保持、明示削除、Git 管理境界を定義する。
- [ ] `SPEC_CONTEXT_COMPRESSION.md` を追加し、Headroom を含む optional backend の使用判断を定義する。
- [ ] `spec-index.yaml.jinja` に agent logging と context compression の conditional routing を追加する。
- [ ] `AGENTS.md.jinja` と開発フロー文書に、raw log はローカル証跡であり主記録ではないことを反映する。
- [ ] `context-compress.sh` を追加し、Headroom がある場合だけ圧縮を試す薄い wrapper にする。
- [ ] Copier 生成テストと smoke test を更新する。
- [ ] `scripts/lint-project-workflow.sh` と `tests/smoke.sh` を実行する。

## Open Decisions

- None.

## Validation Notes

この計画を実装するときは、生成先に余計な必須依存を追加していないことを確認する。

Headroom が未導入の環境でも、生成先の通常 workflow、plan lint、smoke test が通ることを確認する。
