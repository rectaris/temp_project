# Codex CI Autofix

## Goal

CI 失敗時に Codex が安全な範囲で自己修正を試せる GitHub Actions workflow を、リポジトリ本体と Copier テンプレートに追加する。

## Tasks

- [x] 既存 CI と project type を確認する。
- [x] 通常 CI に manual dispatch を追加する。
- [x] Codex CI autofix workflow と prompt を追加する。
- [x] 生成先テンプレートへ同じ workflow、prompt、運用ドキュメント、AGENTS ルールを追加する。
- [x] template static check と smoke test を更新して検証する。

## Validation

- `python3 -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(p).read_text()) for p in ['.github/workflows/ci.yml','.github/workflows/codex-ci-autofix.yml','template/.github/workflows/ci.yml','template/.github/workflows/codex-ci-autofix.yml']]; print('yaml parse passed')"`
- `scripts/lint-project-workflow.sh`
- `git diff --check`
- `tests/smoke.sh`
- `tests/test-hooks.py`
- `tests/copier-update.sh`

## Notes

- `actionlint` は PATH 上に無かったため実行していない。
- `python3 template/scripts/security-static-check.py` は今回触っていない `tests/test-hooks.py` の既存 fixture 文字列に反応して失敗した。
