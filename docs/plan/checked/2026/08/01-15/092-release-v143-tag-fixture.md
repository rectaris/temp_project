# Release v1.4.3 after tag-context Copier fixture failure

status: checked
task_types:
  - planning_docs
  - template_workflow
  - external_services
review_class: C
human_design_required: yes
human_approval_status: approved
implementation_risk: low
implementation_ambiguity: low
write_scope:
  - tests/copier-update.sh
  - CHANGELOG.md
  - README.md
  - docs/plan/
context_files:
  - AGENTS.md
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - references/template-development.md
  - docs/plan/checked/2026/08/01-15/090-release-v142.md
required_specs:
  - docs/agent/SPEC_EXTERNAL_SERVICES.md
  - docs/agent/SPEC_JAPANESE_TECH_WRITING.md
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - docs/agent/SPEC_USER_COMMUNICATION.md
validation:
  - UV_CACHE_DIR=.uv-cache uv sync
  - UV_CACHE_DIR=.uv-cache uv run copier --version
  - scripts/lint-project-workflow.sh
  - REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh
  - python3 tests/test-hooks.py
  - tests/copier-update.sh --require-copier
  - REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh
  - python3 scripts/check-yaml.py .
  - REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .
  - python3 scripts/validate-changes.py --all
  - git diff --check
acceptance:
  - Replace only the `v1.4.2` tag inside the temporary Copier update source clone so a checkout that already contains the published tag reaches the intended migration fixture commit.
  - Preserve the published `v1.4.2` tag and do not publish a GitHub Release for it after its failed tag workflow.
  - Keep an empty Unreleased section and add a 2026-08-15 v1.4.3 entry that identifies the tag-context fixture correction.
  - Update README fixed stable-version examples from v1.4.2 to v1.4.3 without changing external link targets.
  - Complete release validation with the local `v1.4.2` tag present and resolve conflicts, rejection files, backup artifacts, or unclassified tracked-file deletion before publication.
  - Archive this plan and commit release preparation before any post-plan publication operation.
  - Fix post-plan publication targets as `rectaris/temp_project:refs/heads/agent/v143-release-fix`, `rectaris/temp_project:refs/heads/agent/v143-release-fix->refs/heads/main`, `rectaris/temp_project:refs/tags/v1.4.3`, and `rectaris/temp_project:release:v1.4.3`, using the user's current authorization and a fresh external-service gate before each call.
  - Before tagging, verify the merged remote main exact OID in a clean checkout, confirm local and remote `v1.4.3` are unused, create an annotated tag at that OID, and require the tag workflow to pass before publishing the GitHub Release.
checked_summary_ja: 公開済みtagを含むcheckoutでもCopier更新fixtureを完走させ、v1.4.3の公開対象を確定した。

## Decisions

- Use the established fixture-local `git tag -f` pattern because `update_source` is a validated temporary clone and the published source tag must remain untouched.
- Release the correction as v1.4.3 because the published v1.4.2 tag is immutable and its tag workflow failed before the Copier update assertions ran.
- Keep publication outside this plan and use the exact branch, pull-request, tag, and release targets recorded in acceptance.

## Tasks

- [x] Reproduce the tag collision and update only the temporary fixture tag operation.
- [x] Update CHANGELOG and README for v1.4.3.
- [x] Run complete local release validation with v1.4.2 present.
- [x] Record the validated files and post-merge release gates for archive and commit.

## Validation Notes

- Before the fix, `tests/copier-update.sh --require-copier` exited 128 with `fatal: tag 'v1.4.2' already exists`.
- After the fix, `tests/copier-update.sh --require-copier` passed with the published local v1.4.2 tag present and reported only the fixture-local tag replacement.
- `UV_CACHE_DIR=.uv-cache uv sync` passed, and `UV_CACHE_DIR=.uv-cache uv run copier --version` reported Copier 9.15.1.
- `scripts/lint-project-workflow.sh` passed with Actionlint 1.7.12 available on `PATH`.
- `REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` passed.
- `python3 tests/test-hooks.py` passed 34 tests.
- Python 3.11.12 passed `REQUIRE_MINIMUM_COMPAT=1 tests/copier-minimum.sh` with Copier 9.6.0.
- `python3 scripts/check-yaml.py .` parsed 33 YAML files, and `REQUIRE_ACTIONLINT=1 scripts/lint-github-actions.sh .` passed.
- `python3 scripts/validate-changes.py --all` and `git diff --check` passed.
- No unresolved index entry, tracked conflict, `*.rej`, `*.orig`, `*.backup`, or `*.pre-*` release blocker exists outside ignored tool/cache directories.
- `pyproject.toml` remains unchanged at the `0.0.0` placeholder version, and no file mode or symbolic-link change is present.
- README changes only the three fixed stable-version examples from v1.4.2 to v1.4.3 and preserves every external URL target.
- Local and remote v1.4.3 tag names, the remote release branch, and the GitHub Release name are unused.
- Two independent read-only reviews found no High, Medium, or Low blocker before authoritative validation.
