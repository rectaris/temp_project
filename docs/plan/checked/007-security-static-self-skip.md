# Security Static Self Skip

## Goal

生成先の `security-static-check.py` が自分自身の検査ルール文字列に反応して false positive になる問題を防ぐ。

## Tasks

- [x] `template/scripts/security-static-check.py` で自己ファイルを scan 対象から除外する。
- [x] テンプレート lint と Copier smoke/update を実行する。
- [x] 完了記録を checked に移す。

## Validation

- `scripts/lint-project-workflow.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/smoke.sh`
- `PATH=$PWD/.uv-home/.local/bin:$PATH REQUIRE_COPIER=1 tests/copier-update.sh`
