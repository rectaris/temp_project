# Make the shell and sandboxed-worker test fixtures independent of the maintainer host's Git identity and Python location

status: checked
primary_invariant: A repository test fails only for a repository defect, never because the executing account happens to lack a Git identity or to run a Python that lives outside the sandbox's trusted system path.
task_types:
  - template_workflow
review_class: B
human_design_required: no
human_approval_status: not_required
implementation_tier: 1
implementation_risk: low
implementation_ambiguity: low
plan_purpose: implementation
feasibility_evidence:
  - {"evidence":"Run 34350375468 failed tests/smoke.sh with 'empty ident name not allowed' and failed 9 sandboxed worker tests with 'worker exited with 1'. Running the same suite under /home/rectaris/.local/share/uv/python/cpython-3.12.10-linux-x86_64-gnu/bin/python3.12 reproduces exactly those 9 failures locally, and the ordinary system interpreter hides them.","kind":"reproduced_defect"}
  - {"evidence":"tests/smoke.sh already configures a fixture Git identity immediately after git init at its whitespace fixture, and tests/copier-update.sh configures one for every fixture repository, so the missing identity at the execution-group fixture is a gap in an established pattern rather than a new mechanism.","kind":"existing_mechanism"}
  - {"evidence":"scripts/run-sandboxed-plan-worker.py exposes only /usr, /bin, /sbin, /lib and /lib64 inside the sandbox, so replacing the fake Codex fixture's ambient interpreter shebang with one resolved on that trusted system path is the same substitution the runner already relies on for validation executables.","kind":"mechanical_transformation"}
completion_conditions:
  - The fake Codex fixture resolves its interpreter on the sandbox's trusted system path, so the sandboxed worker suite passes under an interpreter installed outside that path.
  - Every fixture repository tests/smoke.sh commits into carries its own Git identity, so the suite passes on an account with no configured identity.
completion_witness_map:
  - {"condition_sha256":"sha256:1fdf01ab31311f4c88c9865f74aef48de5a22e2de8d3f647a02335ce024e2d25","witness":"python3 tests/test-sandboxed-plan-worker.py"}
  - {"condition_sha256":"sha256:36f31986b3e49b9825da62f644a86a7b0a57c5d858818253f7283c5e88f906df","witness":"python3 tests/test-sandboxed-plan-worker.py"}
write_scope:
  - tests/test-sandboxed-plan-worker.py
  - tests/smoke.sh
preservation_scope:
  - none
context_files:
  - AGENTS.md
  - tests/copier-update.sh
  - scripts/run-sandboxed-plan-worker.py
required_specs:
  - docs/agent/SPEC_PLAN_WORKFLOW.md
  - docs/agent/SPEC_SECURITY.md
  - references/validation.md
focused_validation:
  - python3 tests/test-sandboxed-plan-worker.py
validation:
  - scripts/lint-project-workflow.sh
  - tests/smoke.sh
acceptance:
  - The repository test suites fail only for repository defects, so an account without a Git identity or with a managed Python installation observes the same result a maintainer machine observes.
validation_witness_schema: 1
validation_witness_map:
  - {"acceptance_sha256":"sha256:88313d6454393fc39620b3de122bf4032c8d3889d0dbb186a368a48d0128eda1","stage":"focused","witness":"python3 tests/test-sandboxed-plan-worker.py"}
checked_summary_ja: シェル試験とサンドボックス試験の資材を、保守者ホストの Git 識別子と Python 位置から独立させる

## Decisions

- Resolve the fake Codex fixture's interpreter through the trusted system path rather than binding the ambient interpreter into the sandbox, because widening the sandbox's exposed paths for a test fixture would weaken the isolation the runner exists to provide.
- Use one unconditional fixture shebang rather than one that varies with the executing interpreter, so every machine exercises the same fixture instead of the maintainer machine exercising an easier path than continuous integration.
- Give the execution-group fixture repository its own Git identity, matching the identity the neighbouring fixtures already configure, rather than requiring an identity from the executing account.
- Leave scripts/run-sandboxed-plan-worker.py unchanged, because its existing runtime-root binding already reaches a real interpreter installation outside the system path and only the fixture's shebang was unreachable.

## Tasks

- [x] Resolve the fake Codex fixture's interpreter on the sandbox's trusted system path.
- [x] Give the execution-group fixture repository its own Git identity.
- [x] Run the focused witness under an interpreter installed outside the trusted system path, then the authoritative suite once without a configured Git identity.

## Validation Notes

- 焦点証人 `python3 tests/test-sandboxed-plan-worker.py` を、信頼済みシステム経路の外にある `cpython-3.12.10` インタプリタで実行し 147 件すべて成功した。同じインタプリタで修正前の資材を実行すると、CI が報告した 9 件と同一の失敗が再現する。
- 権威検証は `scripts/lint-project-workflow.sh` と、`GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null REQUIRE_ACTIONLINT=1 REQUIRE_COPIER=1 tests/smoke.sh` を各 1 回実行し、いずれも通過した。後者は Git 識別子を持たないアカウントを再現している。
- lint 出力中の `root agent policy check failed:` 行は否定試験の期待出力である。
